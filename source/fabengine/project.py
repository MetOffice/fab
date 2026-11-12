from __future__ import annotations

from pathlib import Path


# Todo: Given that they share "paths" it may be that Project and Repository
#       are aspects of the same concept.
#
class Project:
    """
    Represents a software project.
    """

    def __init__(
        self,
        project_dir: Path,
        identifier: str | None = None,
        source_dir=Path("source"),
        source_include: list[Path] | None = None,
        source_encoding: str | None = None,
        paths: dict[str, Path] | None = None,
        unit_test_dir: Path = Path("unit-test"),
        configuration_meta_data: Path = Path("rose-meta"),
        force_include_dir: list[Path] | None = None,
    ):
        """
        :param project_dir: Directory holding project.
        :param identifier: Identifying name, defaults to directory leaf name.
        :param source_dir: Project subdirectory holding source, defaults to
                           ``source``.
        :param source_include: List of paths to be extracted from the project.
                               If not specified, everything is imported.
                               ``source``.
        :param unit_test_dir: Project subdirectory holding unit tests, defaults
                              to ``unit-test``.
        :param paths: Mapping of repository executables to tool names.
        :param configuration_meta_data: Project subdirectory holding
                                        configuration metadata, defaults to
                                        ``rose-meta``.
        """
        self._project_dir = project_dir
        self._identifier = identifier or self._project_dir.name
        self._source_dir = source_dir
        self._source_include = source_include
        self._source_encoding = source_encoding or "utf-8"
        self._force_include_dir = force_include_dir or []

        # Todo: This is a fix for the immediate problem of finding the
        #       build tools, configurator and templaterator. It may well
        #       be replaced by whatever we develop to manage compilers.
        #
        self._paths = paths or {}
        self._unit_test_dir = unit_test_dir
        self._configuration_meta_data = configuration_meta_data

    @property
    def identifier(self) -> str:
        """
        Gets identifying name.
        """
        return self._identifier

    @property
    def project_dir(self) -> Path:
        """
        Gets project directory.
        """
        return self._project_dir

    @property
    def source_dir(self) -> Path:
        """
        Gets full source directory, including project directory.
        """
        return self._project_dir / self._source_dir

    @property
    def source_include(self) -> list[Path] | None:
        return self._source_include

    @property
    def source_encoding(self) -> str:
        return self._source_encoding

    @property
    def paths(self) -> dict[str, Path]:
        return self._paths

    @property
    def force_include_dir(self) -> list[Path]:
        return self._force_include_dir

    @property
    def unit_test_dir(self) -> Path:
        """
        Gets full unit test directory, including project directory.
        """
        return self._project_dir / self._unit_test_dir

    @property
    def configuration_meta_data(self) -> Path:
        """
        Gets full metadata directory, including project directory.
        """
        return self._project_dir / self._configuration_meta_data
