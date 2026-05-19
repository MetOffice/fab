from multiprocessing import get_logger as mp_get_logger
from pathlib import Path
from re import compile as re_compile, IGNORECASE
from typing import Any, Iterable

from fabengine.actions import (
    Action,
    SubprocessAction,
    Prerequisite,
)
from fabengine.prerequisite import FilePrerequisite
from fabengine.actions.fortran import AnalyseFortran
from fabengine.database import Database


class RosePickerPrerequisite(Prerequisite):
    """
    Manages prerequisites of a "Rose Picker" action.
    """

    def __init__(self, filename: Path, database: Database):
        """
        :param filename: Top level ``rose-meta.conf`` file
        :param database: Build state and configuration.
        """
        self._filename = filename
        self._database = database

    def __str__(self) -> str:
        return "RosePicker prerequisites: " + str(self._filename)

    _IMPORT_PATTERN = re_compile(r"import\s*=\s*(.*)", IGNORECASE)
    _ADDITIONAL_PATTERN = re_compile(r"\s*=\s*(.*)", IGNORECASE)

    def _scan_meta(self, filename: Path) -> Iterable[Path]:
        buffer = ""
        state = "scan"
        for line in filename.read_text().splitlines():
            if state == "scan":
                match = self._IMPORT_PATTERN.match(line)
                if match:
                    buffer += match.group(1) + " "
                    state = "more"

            elif state == "more":
                match = self._ADDITIONAL_PATTERN.match(line)
                if match:
                    buffer += match.group(1) + " "
                else:  # No match
                    break  # We are done
        return [Path(path) for path in buffer.split()]

    def ready(self) -> bool:
        """
        Determines readiness of RosePicker action.

        The action is considered ready when the top level ``rose-meta.conf``
        file and all those it includes have been found.
        """
        if not self._filename.exists():
            return False

        okay = True
        import_files = [self._filename]
        while import_files:
            meta_file = import_files.pop()
            mp_get_logger().debug("Examining: " + str(meta_file))
            imports = self._scan_meta(meta_file)
            for head in imports:
                found = False
                mp_get_logger().debug("Considering: " + str(head))
                for root in self._database.config_meta_dirs:
                    test_name = root / head / "rose-meta.conf"
                    mp_get_logger().debug(
                        f"Possible ({test_name.exists()}): {test_name}"
                    )
                    if test_name.exists():
                        import_files.append(test_name)
                        found = True
                        break  # for root in self._database.config_meta_dirs
                okay &= found
                if not okay:
                    break  # for head in imports
            if not okay:
                break  # while import_files

        return okay


class RosePicker(SubprocessAction):
    """
    Converts configuration metadata to intermediate file.

    The convertion to an intermediate format is necessary to manage licencing
    issues.

    .. todo:: Get a new starter to make a clean-room implementation of meta
              file parser so we can stop using "rose picker."
    """

    def __init__(self, filename: Path, database: Database):
        """
        :param filename: Top level ``rose-meta.conf`` file.
        :param database: Build state and configuration.
        """
        self._filename = filename
        self._database = database

        self._configuration_dir = (
            self._database.config["paths"]["build_dir"] / "configuration"
        )
        self._configuration_dir.mkdir(parents=True, exist_ok=True)

        arguments = [self._filename, "-directory", self._configuration_dir]
        super().__init__(Path("rose_picker"), arguments)

    def __str__(self) -> str:
        return f"Rose picking: {self._filename.name}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: All prerequisites of action.
        :rtype: Iterable[RosePickerPrerequisite]
        """
        return [RosePickerPrerequisite(self._filename, self._database)]

    def perform(self) -> Iterable[Action]:
        """
        Performs "Rose Picker" action.

        Generates :class:`ConfigurationLoader` and :class:`NamelistLoader`
        actions to operate on resulting intermediate files.
        """
        arguments = []
        for directory in self._database.config_meta_dirs:
            arguments.extend(["-include_dirs", directory])
        self.run_subprocess(additional_arguments=arguments)
        return [
            ConfigurationLoader(
                self._configuration_dir / "config_namelists.txt",
                self._database,
            ),
            NamelistType(
                self._configuration_dir / "rose-meta.json",
                self._configuration_dir / "config_namelists.txt",
                self._database,
            ),
        ]


class ConfigurationLoader(SubprocessAction):
    """
    Generates Fortran source to load full configuration.
    """

    def __init__(self, filename: Path, database: Database):
        """
        :param filename: Location of ``config_namelists.txt`` file from Rose
                         Picker.
        :param database: Build state and configuration.
        """
        self._filename = filename
        self._database = database

        self._output_dir = self._database.config["paths"]["build_dir"]
        arguments: list[Any] = ["-o", self._output_dir]

        for line in self._filename.read_text().splitlines():
            for namelist in line.split():
                arguments.append(namelist)

        super().__init__(
            self._database.config["paths"]["generate-config-loader"], arguments
        )

    def __str__(self) -> str:
        return f"Configuration loader: {self._filename}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets all prerequisites.

        :return: Requirement on ``config_namelists.txt`` file.
        :rtype: Iterable[FilePrerequisite]
        """
        return [FilePrerequisite(self._filename)]

    def perform(self) -> Iterable[Action]:
        """
        Perform action.

        :return: Action to analyse resulting Fortran source.
        """
        self.run_subprocess()
        return [
            AnalyseFortran(self._output_dir / "config_loader_mod.f90", self._database)
        ]


class NamelistType(SubprocessAction):
    """
    Generates Fortran source to load namelists.
    """

    def __init__(self, json_file: Path, namelist_file: Path, database: Database):
        """
        .. todo:: Change namelist generation to be done namelist at a time.

        :param json_file: Location of ``rose-meta.json`` generated by Rose
                          Picker.
        :param namelist_file: Location of ``config_namelists.txt`` generated
                              by Rose Picker.
        :param database: Build state and configuration.
        """
        self._json_file = json_file
        self._namelist_file = namelist_file
        self._database = database

        self._config_dir = self._database.config["paths"]["build_dir"] / "configuration"

        arguments = [self._json_file, "-directory", self._config_dir]
        super().__init__(
            self._database.config["paths"]["generate-extended-namelist-type"],
            arguments,
        )

    def __str__(self) -> str:
        return f"Namelist loader: {self._json_file}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: Prerequisites on ``rose-meta.json`` and
                 ``config_namelists.txt`` files.
        :rtype: Iterable[FilePrerequisite]
        """
        return [
            FilePrerequisite(self._json_file),
            FilePrerequisite(self._namelist_file),
        ]

    def perform(self) -> list[Action]:
        """
        Perform action.

        :return: Action to analyse resulting Fortran source.
        """
        self.run_subprocess()

        actions: list[Action] = []
        for line in self._namelist_file.read_text().splitlines():
            for namelist in line.split():
                leafname = namelist + "_nml_mod.f90"
                actions.append(
                    AnalyseFortran(self._config_dir / leafname, self._database)
                )
        actions.append(
            NamelistLoader(self._json_file, self._namelist_file, self._database)
        )
        return actions


class ConfigType(SubprocessAction):
    """
    Generates Fortran source to load a namelist file.
    """

    def __init__(
        self,
        namelist_file: Path,
        duplicates_file: Path,
        database: Database,
    ):
        """
        .. todo:: Change namelist generation to be done namelist at a time.
        """
        self._namelist_file = namelist_file
        self._duplicates_file = duplicates_file
        self._database = database

        self._config_dir = self._database.config["paths"]["build_dir"] / "configuration"

        arguments = ["-o", self._config_dir]

        for line in self._duplicates_file.read_text().splitlines():
            if not line:
                continue
            arguments.extend(["-duplicate", line.strip()])

        for line in self._namelist_file.read_text().splitlines():
            if not line:
                continue
            arguments.append(line.strip())

        super().__init__(
            self._database.config["paths"]["generate-config-type"], arguments
        )

    def __str__(self) -> str:
        return f"Namelist file loader <{self._namelist_file}>"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: Prerequisites on namelist and duplicate files.
        :rtype: Iterable[FilePrerequisite]
        """
        return [
            FilePrerequisite(self._namelist_file),
            FilePrerequisite(self._duplicates_file),
        ]

    def perform(self) -> list[Action]:
        """
        Perform action.

        :return: Action to analyse resulting Fortran source.
        """
        self.run_subprocess()

        return [AnalyseFortran(self._config_dir / "config_mod.f90", self._database)]


class NamelistLoader(SubprocessAction):
    """
    Generates Fortran source to load a namelist file.

    .. todo:: Change namelist generation to be done namelist at a time.
    """

    def __init__(self, json_file: Path, namelist_file: Path, database: Database):
        """
        :param json_file: Location of ``rose-meta.json`` generated by Rose
                          Picker.
        :param namelist_file: Location of ``config_namelists.txt`` generated
                              by Rose Picker.
        :param database: Build state and configuration.
        """
        self._json_file = json_file
        self._namelist_file = namelist_file
        self._database = database

        self._config_dir = self._database.config["paths"]["build_dir"] / "configuration"

        arguments = [self._json_file, "-directory", self._config_dir]
        super().__init__(
            self._database.config["paths"]["generate-namelist-loader"], arguments
        )

    def __str__(self) -> str:
        return f"Namelist file loader <{self._json_file}>"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: Prerequisites on ``rose-meta.json`` and
                 ``config_namelists.txt`` files.
        :rtype: Iterable[FilePrerequisite]
        """
        return [
            FilePrerequisite(self._json_file),
            FilePrerequisite(self._namelist_file),
        ]

    def perform(self) -> list[Action]:
        """
        Perform action.

        :return: Action to analyse resulting Fortran source.
        """
        self.run_subprocess()

        actions: list[Action] = [
            ConfigType(
                self._namelist_file,
                self._config_dir / "duplicate_namelists.txt",
                self._database,
            )
        ]
        for line in self._namelist_file.read_text().splitlines():
            for namelist in line.split():
                leafname = namelist + "_config_mod.f90"
                actions.append(
                    AnalyseFortran(self._config_dir / leafname, self._database)
                )
        return actions
