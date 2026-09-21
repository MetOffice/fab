from collections.abc import Iterable
from io import BytesIO
from pathlib import Path
from tarfile import REGTYPE, TarInfo
from tarfile import open as tar_open
from time import time

from yaml import dump as yaml_dump

from fabengine.actions import Action, Prerequisite
from fabengine.database import Database

METAFILE = "METADATA.yaml"


class CreateArchive(Action):
    """Action to save the work directory to a tar archive.

    :param filename: Name of the tar file being created.
    :param database: State and configuration database.
    """

    def __init__(self, filename: Path, database: Database):
        super().__init__(f"archive {filename}")
        self._filename = Path(filename)
        self._database = database
        self._work_dir = Path(database.configuration["paths"]["work_dir"])
        self._relative_dir = Path(str(self._work_dir).lstrip("/"))

        suffix = self._filename.suffix.lstrip(".")
        if suffix == "tar":
            self._compression = ""
        elif suffix in ("gz", "bz2", "xz", "zst"):
            self._compression = str(suffix)
        else:
            raise ValueError(f"{filename} does not have a valid suffix")

    def prerequisites(self) -> Iterable[Prerequisite]:
        """Action dependencies."""
        # todo: this should really depend on whether all other actions
        # have been completed.  For now, just run as a standalone item
        # at the end of fab_core()
        return []

    def perform(self) -> list[Action]:
        """Create the tar archive."""

        # Type checking complains about no overload variant matches
        # argument types, so disable checking
        with tar_open(self._filename, mode=f"w:{self._compression}") as tarfile:  # type: ignore
            tarfile.add(self._work_dir, filter=self._addition_filter)
            tarfile.addfile(*self._create_metadata())

        # todo: add to the artefact store?
        return []

    def _addition_filter(self, target: TarInfo) -> TarInfo | None:
        """Filter and adjust file properties in the archive.

        :param target: Candidate for inclusion in the archive.
        :returns: An updated TarInfo if valid for inclusion.
        """

        if not (target.isfile() or target.isdir() or target.issym()):
            # Do not save any unusual file types
            return None

        name = Path(target.name)
        target.name = str(name.relative_to(self._relative_dir))

        if name.suffix == ".nc":  # or name.name == METAFILE:
            # Do not include data files or a previous metadata file
            return None

        # Do not leak user credentials
        target.uid = 0
        target.gid = 0

        return target

    def _create_metadata(self):
        """Add a metadata file to the archive."""

        # todo: include some useful metadata
        text = yaml_dump(
            {
                "timestamp": int(time()),
            }
        )
        contents = BytesIO(text.encode("utf-8"))

        info = TarInfo(str(METAFILE))
        info.size = len(contents.getbuffer())
        info.mtime = int(time())
        info.mode = 0o0644
        info.type = REGTYPE

        return info, contents
