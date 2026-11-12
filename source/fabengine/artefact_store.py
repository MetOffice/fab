"""
Implements a virtual filesystem which allows static source files and
transitory build files to be managed in the same namespace.

.. todo:: Implementation is messy and needs to be rationalised.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Artefact metadata keys used by the build framework:
#
ENCODING_META = "encoding"


class ArtefactStore:
    """
    Virtual filesystem for managing compile artefacts.

    Maps static files and intermediate files into a single namespace.
    """

    def __init__(self, intermediate_dir: Path):
        """
        :param intermediate_dir: Directory for storing intermediate files.
        """
        self._intermediate_dir = intermediate_dir
        self._intermediate_dir.mkdir(parents=True, exist_ok=True)

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


class ArtefactPath(Path):
    def __init__(self, *args: str | Path):
        super().__init__(*args)

        if self.is_absolute():
            raise ValueError(f"Artefact filenames must be relative: {self}")
