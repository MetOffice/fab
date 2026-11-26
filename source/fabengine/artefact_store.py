"""
Implements a virtual filesystem which allows static source files and
transitory build files to be managed in the same namespace.

.. todo:: Implementation is messy and needs to be rationalised.
"""

from __future__ import annotations

from hashlib import file_digest
from os import stat_result
from pathlib import Path
from typing import Any

from fabengine.actions import TwoPartPath

# Artefact metadata keys used by the build framework:
#
ENCODING_META = "encoding"


class ArtefactStore:
    """
    Virtual filesystem for managing compile artefacts.

    Maps static files and intermediate files into a single namespace.
    """

    _digest_mode = "sha256"

    def __init__(self, intermediate_dir: Path, fresh_build: bool = False):
        """
        :param intermediate_dir: Directory for storing intermediate files.
        :param fresh_build: do not reuse anything if True.
        """
        self._intermediate_dir = intermediate_dir
        self._intermediate_dir.mkdir(parents=True, exist_ok=True)
        self._fresh_build = fresh_build

        self._map: dict[Path, Artefact] = {}

    def __len__(self) -> int:
        return len(self._map)

    def __iter__(self):
        yield from self._map.values()

    @property
    def intermediate_dir(self) -> Path:
        """
        Gets the root of the intermediate file tree.
        """
        return self._intermediate_dir

    def dump_map(self) -> None:
        """
        Dumps map information to a stream.

        This is intended for debug purposes only.
        """
        with open("artefact_map.txt", "wt") as stream:
            for virtual_filename, artefact in self._map.items():
                print(f"{virtual_filename}: {artefact.real_filename}", file=stream)

    def map_file(self, real_filename: Path, virtual_filename: ArtefactPath, **kwargs):
        if virtual_filename in self._map:
            raise RuntimeError(
                f"Attempted to map <{real_filename}> to <{virtual_filename}>"
                f" but <{self._map[virtual_filename].real_filename}> already does."
            )
        self._map[virtual_filename] = Artefact(
            virtual_filename, real_filename, **kwargs
        )

    def notice_file(self, virtual_filename: ArtefactPath, **kwargs) -> None:
        """
        Notifies the artefact store that a file has been added to it.

        This is only used when a process is doing something sneaky.
        Most of the time `get_artefact()` is the preferred route. It will
        throw an error if the file does not, in fact, exist.
        """
        real_filename = self._intermediate_dir / virtual_filename
        if real_filename.exists():
            self._map[virtual_filename] = Artefact(
                virtual_filename, real_filename, **kwargs
            )
        else:
            raise RuntimeError(f"Asked to notice nonexistent file <{virtual_filename}>")

    def make_virtual_path(self, virtual_filename: ArtefactPath) -> Path:
        """Potential path to a virtual file.

        Get a path before a file is added with notice_file.
        """
        return self._intermediate_dir / virtual_filename

    def exists(self, virtual_filename: ArtefactPath) -> bool:
        """
        Determines if an artefact is in the store.
        """
        if virtual_filename in self._map:
            return self._map[virtual_filename].real_filename.exists()
        else:
            return False

    def ensure_directory(self, virtual_filename: ArtefactPath) -> Path:
        """
        Ensures that a directory exists in the virtual filesystem.

        :return: Path of the actual directory.
        """
        full_filename = self._intermediate_dir / virtual_filename
        full_filename.mkdir(parents=True, exist_ok=True)
        return full_filename

    def set_artefact(self, artefact: Artefact) -> None:
        self._map[artefact.virtual_filename] = artefact

    def get_artefact(self, virtual_filename: ArtefactPath) -> Artefact:
        """
        Retrieves an artefact from the store.

        If it is not in the store, create it in the intermediate directory.
        """
        if virtual_filename not in self._map:
            new_filename = self._intermediate_dir / virtual_filename

            # Ensure directory tree
            new_filename.parent.mkdir(parents=True, exist_ok=True)

            # New file
            self._map[virtual_filename] = Artefact(virtual_filename, new_filename)
        return self._map[virtual_filename]

    def promote_artefact(self, virtual_filename: ArtefactPath) -> Artefact:
        """
        Promotes a mapping to a symlink. This makes it appear as a file in the
        workspace without requiring a copy.

        If the artefact already exists in the workspace (as a file or link)
        it is just returned.
        """
        workspace_filename = self._intermediate_dir / virtual_filename
        if not workspace_filename.exists():
            workspace_filename.parent.mkdir(parents=True, exist_ok=True)
            workspace_filename.symlink_to(self._map[virtual_filename].real_filename)
            self._map[virtual_filename] = Artefact(virtual_filename, workspace_filename)

        return self._map[virtual_filename]

    def status(self, target: ArtefactPath | Path | TwoPartPath) -> stat_result | None:
        """Get the status of a file."""
        if isinstance(target, ArtefactPath):
            if (artefact := self._map.get(target)) is None:
                return None
            target = artefact.real_filename
        elif isinstance(target, TwoPartPath):
            target = target.full
        elif not isinstance(target, Path):
            raise TypeError(f"invalid target path: {target}")

        if not target.exists():
            return None

        return target.stat()

    def digest(self, target: ArtefactPath | Path | TwoPartPath) -> str | None:
        """Hex digest of a hash of the file contents."""
        if isinstance(target, ArtefactPath):
            if (artefact := self._map.get(target)) is None:
                return None
            target = artefact.real_filename
        elif isinstance(target, TwoPartPath):
            target = target.full
        elif not isinstance(target, Path):
            raise TypeError(f"invalid target path: {target}")

        if not target.is_file():
            return None

        return file_digest(target.open("rb"), self._digest_mode).hexdigest()

    def reusable_digests(self, first: list[str], second: list[str]) -> bool:
        """Whether the lists of digests match and can be reused."""

        if self._fresh_build:
            # Never reuse anything if running in fresh mode
            return False

        if len(first) != len(second):
            raise IndexError("argument lists are different sizes")

        for i in range(len(first)):
            if first[i] is None or second[i] is None or first[i] != second[i]:
                return False

        return True

    def reusable(
        self,
        inputs: list[Any],
        outputs: list[Any],
    ) -> bool:
        """Whether the virtual file can be reused as a dependency.

        Items can be reused if the build system is running in
        incremental mode and if the inputs have not changed relative
        to the outputs.
        """

        if self._fresh_build:
            # Never reuse anything if running in fresh mode
            return False

        # todo: implement with something other than timestamps

        # Find the most recently changed input file
        newest_input = -1.0
        for target in inputs:
            status = self.status(target)
            if status is None:
                return False
            newest_input = max(newest_input, status.st_mtime)

        # Find the oldest output file
        oldest_output = 1.0e20
        for target in outputs:
            status = self.status(target)
            if status is None:
                return False
            oldest_output = min(oldest_output, status.st_mtime)

        return newest_input < oldest_output

    def valid(self, source: Artefact) -> bool:
        """Whether the file has changed relative to its past self.

        If running in fresh mode or if no previous status is
        available, file is never valid for reuse.  If running in
        incremental mode, file is only fresh if it predates its
        former self.
        """

        if self._fresh_build:
            # Never valid for reuse if running in fresh mode
            return False

        # todo: support something other than timestamps
        previous_status = source.get_meta("mtime", None)
        if previous_status is None:
            # Not valid if no previous comparison is available
            return False

        status = self.status(source.real_filename)
        if status is None:
            return False

        return previous_status <= status.st_mtime

    def as_list(self) -> list[dict[str, Any]]:
        """Convert instance into a serialiable list."""
        return [i.as_dict() for i in self._map.values()]

    def load_list(self, values: list[dict[str, Any]]) -> None:
        """Populate from a list of serialised values.

        Any metadata keys that start with a double underscore stripped
        out before each Artefact is added, allowing them to be used as
        transient properties.  They are dumped out to help with
        debugging.
        """

        for entry in values:
            meta = {
                k: v for k, v in entry.get("meta", {}).items() if not k.startswith("__")
            }
            self.map_file(
                Path(entry["real_filename"]),
                ArtefactPath(entry["virtual_filename"]),
                **meta,
            )


# Todo: Can we do away with "Artefact" and just use "ArtefactPath"?
#
class Artefact:
    def __init__(self, virtual_filename: ArtefactPath, real_filename: Path, **kwargs):
        self._virtual_filename = virtual_filename
        self._real_filename = real_filename
        self._meta: dict[str, Any] = {k: v for k, v in kwargs.items()}

    @property
    def virtual_filename(self) -> ArtefactPath:
        return self._virtual_filename

    @property
    def real_filename(self) -> Path:
        return self._real_filename

    @property
    def name(self) -> str:
        return self._virtual_filename.name

    def set_meta(self, key: str, value: Any) -> None:
        self._meta[key] = value

    def get_meta(self, key: str, default: Any = None) -> Any:
        return self._meta.get(key, default)

    def read_text(self) -> str:
        """
        Gets the textual content of the artefact.

        This is a convenience method to neaten up calling code.

        .. todo:: If Artefact and ArtefactPath were combined this would be
                  redundant as Path already provides it.
        """
        return self.real_filename.read_text()

    def write_text(self, text: str) -> None:
        """
        Writes text into an artefact.

        This is a convenience method to neaten up calling code.

        .. todo:: If Artefact and ArtefactPath were combined this would be
                  redundant as Path already provides it.
        """
        self.real_filename.write_text(text)

    def as_dict(self) -> dict[str, Any]:
        """Convert instance into a serialisable dictionary."""

        return {
            "virtual_filename": str(self._virtual_filename),
            "real_filename": str(self._real_filename),
            "meta": {k: v for k, v in self._meta.items()},
        }


class ArtefactPath(Path):
    def __init__(self, *args: str | Path):
        super().__init__(*args)

        if self.is_absolute():
            raise ValueError(f"Artefact filenames must be relative: {self}")
