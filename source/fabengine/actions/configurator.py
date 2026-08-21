from collections.abc import Iterable
from pathlib import Path
from re import IGNORECASE
from re import compile as re_compile
from typing import Any

from fabengine.actions import (
    Action,
    Prerequisite,
    SubprocessAction,
)
from fabengine.actions.fortran import AnalyseFortran
from fabengine.artefact_store import ArtefactPath
from fabengine.database import Database
from fabengine.prerequisite import ArtefactPrerequisite

_CONFIGURATION_DIR = ArtefactPath("_configuration")
_JSON_FILE = _CONFIGURATION_DIR / "rose-meta.json"
_LIST_FILE = _CONFIGURATION_DIR / "config_namelists.txt"
_LOADER_FILE = _CONFIGURATION_DIR / "config_loader_mod.f90"
_DUPLICATE_FILE = _CONFIGURATION_DIR / "duplicate_namelists.txt"

from fabengine.logserver import make_logger


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

        system_logger = make_logger("system")

        okay = True
        import_files = [self._filename]
        while import_files:
            meta_file = import_files.pop()
            system_logger.debug("Examining: " + str(meta_file))
            imports = self._scan_meta(meta_file)
            for head in imports:
                found = False
                system_logger.debug("Considering: " + str(head))
                for root in self._database.config_meta_dirs:
                    test_name = root / head / "rose-meta.conf"
                    system_logger.debug(f"Possible ({test_name.exists()}): {test_name}")
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

        configuration_dir = self._database.artefact_store.ensure_directory(
            _CONFIGURATION_DIR
        )
        arguments = [self._filename, "-directory", configuration_dir]
        super().__init__(Path("rose_picker"), arguments)

    def __str__(self) -> str:
        return f"Rose picking: {self._filename}"

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

        Generates :class:`ConfigurationLoader`, :class:`NamelistLoader` and
        :class:NamelistType` actions to operate on resulting intermediate
        files.
        """
        arguments: list[str | Path] = []
        for directory in self._database.config_meta_dirs:
            arguments.extend(["-include_dirs", directory])
        self.run_subprocess(additional_arguments=arguments)
        self._database.artefact_store.notice_file(_LIST_FILE)
        self._database.artefact_store.notice_file(_JSON_FILE)
        return [
            ConfigurationLoader(_LIST_FILE, self._database),
            NamelistType(_JSON_FILE, _LIST_FILE, self._database),
            NamelistLoader(_JSON_FILE, _LIST_FILE, self._database),
            FeignConfiguration(_JSON_FILE, self._database),
        ]


class ConfigurationLoader(SubprocessAction):
    """
    Generates Fortran source to load full configuration.
    """

    def __init__(self, filename: ArtefactPath, database: Database):
        """
        :param filename: Virtual filename of ``config_namelists.txt`` file from
                         Rose Picker.
        :param database: Build state and configuration.
        """
        self._filename = filename
        self._database = database

        self._configuration_dir = self._database.artefact_store.ensure_directory(
            _CONFIGURATION_DIR
        )
        arguments: list[Any] = ["-o", self._configuration_dir]

        list_artefact = self._database.artefact_store.get_artefact(self._filename)
        for line in list_artefact.read_text().splitlines():
            arguments.extend(line.split())

        super().__init__(
            self._database.configuration["paths"]["generate-config-loader"], arguments
        )

    def __str__(self) -> str:
        return f"Configuration loader: {self._filename}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets all prerequisites.

        :return: Requirement on ``config_namelists.txt`` file.
        """
        return [ArtefactPrerequisite(self._filename, self._database)]

    def perform(self) -> Iterable[Action]:
        """
        Perform action.

        :return: Action to analyse resulting Fortran source.
        """
        self.run_subprocess()

        self._database.artefact_store.notice_file(_LOADER_FILE)
        return [AnalyseFortran(_LOADER_FILE, self._database)]


class NamelistType(SubprocessAction):
    """
    Generates Fortran source to load namelists.
    """

    def __init__(
        self, json_file: ArtefactPath, namelist_file: ArtefactPath, database: Database
    ):
        """
        .. todo:: Change namelist generation to be done namelist at a time.

        :param json_file: Virtual filename of ``rose-meta.json`` generated by
                          Rose Picker.
        :param namelist_file: Virtual filename of ``config_namelists.txt``
                              generated by Rose Picker.
        :param database: Build state and configuration.
        """
        self._json_file = json_file
        self._namelist_file = namelist_file
        self._database = database

        self._configuration_dir = self._database.artefact_store.ensure_directory(
            _CONFIGURATION_DIR
        )
        json_artefact = self._database.artefact_store.get_artefact(self._json_file)
        arguments = [json_artefact.real_filename, "-directory", self._configuration_dir]
        super().__init__(
            self._database.configuration["paths"]["generate-extended-namelist-type"],
            arguments,
        )

    def __str__(self) -> str:
        return f"Namelist loader: {self._json_file}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: Prerequisites on ``rose-meta.json`` and
                 ``config_namelists.txt`` files.
        """
        return [
            ArtefactPrerequisite(self._json_file, self._database),
            ArtefactPrerequisite(self._namelist_file, self._database),
        ]

    def perform(self) -> list[Action]:
        """
        Perform action.

        :return: Action to analyse resulting Fortran source.
        """
        self.run_subprocess()

        actions: list[Action] = []
        list_artefact = self._database.artefact_store.get_artefact(self._namelist_file)
        for line in list_artefact.read_text().splitlines():
            for namelist in line.split():
                virtual_filename = _CONFIGURATION_DIR / f"{namelist}_nml_mod.f90"
                self._database.artefact_store.notice_file(virtual_filename)
                actions.append(AnalyseFortran(virtual_filename, self._database))
        return actions


class ConfigType(SubprocessAction):
    """
    Generates Fortran source to load a namelist file.
    """

    def __init__(
        self,
        namelist_file: ArtefactPath,
        duplicates_file: ArtefactPath,
        database: Database,
    ):
        """
        .. todo:: Change namelist generation to be done namelist at a time.
        """
        self._namelist_file = namelist_file
        self._duplicates_file = duplicates_file
        self._database = database

        configuration_dir = self._database.artefact_store.ensure_directory(
            _CONFIGURATION_DIR
        )
        arguments = ["-o", configuration_dir]

        self._multi_lists: list[str] = []
        duplicates_artefact = self._database.artefact_store.get_artefact(
            self._duplicates_file
        )
        for line in duplicates_artefact.read_text().splitlines():
            if not line:
                continue
            self._multi_lists.append(line.strip())

        for multi_list in self._multi_lists:
            arguments.extend(["-duplicate", multi_list])

        namelist_artefact = self._database.artefact_store.get_artefact(
            self._namelist_file
        )
        for line in namelist_artefact.read_text().splitlines():
            if not line:
                continue
            arguments.append(line.strip())

        super().__init__(
            self._database.configuration["paths"]["generate-config-type"], arguments
        )

    def __str__(self) -> str:
        return f"Namelist file loader <{self._namelist_file}>"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: Prerequisites on namelist and duplicate files.
        """
        return [
            ArtefactPrerequisite(self._namelist_file, self._database),
            ArtefactPrerequisite(self._duplicates_file, self._database),
        ]

    def perform(self) -> list[Action]:
        """
        Perform action.

        :return: Action to analyse resulting Fortran source.
        """
        self.run_subprocess()

        actions: list[Action] = []
        for multi_list in self._multi_lists:
            iterator_path = _CONFIGURATION_DIR / f"{multi_list}_nml_iterator_mod.f90"
            self._database.artefact_store.notice_file(iterator_path)
            actions.append(AnalyseFortran(iterator_path, self._database))

        config_path = _CONFIGURATION_DIR / "config_mod.f90"
        self._database.artefact_store.notice_file(config_path)
        actions.append(AnalyseFortran(config_path, self._database))

        return actions


class NamelistLoader(SubprocessAction):
    """
    Generates Fortran source to load a namelist file.

    .. todo:: Change namelist generation to be done namelist at a time.
    """

    def __init__(
        self, json_file: ArtefactPath, namelist_file: ArtefactPath, database: Database
    ):
        """
        :param json_file: Virtual filename of ``rose-meta.json`` generated by
                          Rose Picker.
        :param namelist_file: Virtual filename of ``config_namelists.txt``
                              generated by Rose Picker.
        :param database: Build state and configuration.
        """
        self._json_file = json_file
        self._namelist_file = namelist_file
        self._database = database

        configuration_dir = self._database.artefact_store.ensure_directory(
            _CONFIGURATION_DIR
        )

        json_artefact = self._database.artefact_store.get_artefact(self._json_file)
        arguments = [json_artefact.real_filename, "-directory", configuration_dir]
        super().__init__(
            self._database.configuration["paths"]["generate-namelist-loader"], arguments
        )

    def __str__(self) -> str:
        return f"Namelist file loader <{self._json_file}>"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: Prerequisites on ``rose-meta.json`` and
                 ``config_namelists.txt`` files.
        """
        return [
            ArtefactPrerequisite(self._json_file, self._database),
            ArtefactPrerequisite(self._namelist_file, self._database),
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
                _DUPLICATE_FILE,
                self._database,
            )
        ]

        list_artefact = self._database.artefact_store.get_artefact(self._namelist_file)
        for line in list_artefact.read_text().splitlines():
            for namelist in line.split():
                virtual_filename = _CONFIGURATION_DIR / f"{namelist}_config_mod.f90"
                self._database.artefact_store.notice_file(virtual_filename)
                actions.append(AnalyseFortran(virtual_filename, self._database))
        return actions


class FeignConfiguration(SubprocessAction):
    def __init__(self, json_file: ArtefactPath, database: Database):
        """
        :param json_file: Location of ``rose-meta.json`` generated by Rose
                          Picker.
        :param database: Build state and configuration.
        """
        self._json_file = json_file
        self._database = database

        self._feign_artefact = self._database.artefact_store.get_artefact(
            _CONFIGURATION_DIR / "feign_config_mod.f90"
        )
        json_artefact = self._database.artefact_store.get_artefact(self._json_file)
        super().__init__(
            self._database.configuration["paths"]["generate-feigns"],
            [json_artefact.real_filename, "-o", self._feign_artefact.real_filename],
        )

    def __str__(self) -> str:
        return f"Configuration feigners <{self._json_file}>"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: Prerequisites on ``rose-meta.json`` files.
        """
        return [
            ArtefactPrerequisite(ArtefactPath(self._json_file), self._database),
        ]

    def perform(self) -> list[Action]:
        """
        Perform action.

        :return: Action to analyse resulting Fortran source.
        """
        self.run_subprocess()
        return [AnalyseFortran(self._feign_artefact.virtual_filename, self._database)]
