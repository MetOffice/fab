from multiprocessing import get_logger as mp_get_logger
from pathlib import Path
from re import compile as re_compile, IGNORECASE
from subprocess import run, PIPE
from typing import Iterable

from fabengine.actions import Action, ActionResult, Prerequisite
from fabengine.prerequisite import FilePrerequisite
from fabengine.actions.fortran import AnalyseFortran
from fabengine.database import Database


class RosePickerPrerequisite(Prerequisite):
    def __init__(self, filename: Path, database: Database):
        self._filename = filename
        self._database = database

    def __str__(self) -> str:
        return "RosePicker prerequisites: " + str(self._filename)

    _IMPORT_PATTERN = re_compile(r'import\s*=\s*(.*)', IGNORECASE)
    _ADDITIONAL_PATTERN = re_compile(r'\s*=\s*(.*)', IGNORECASE)

    def _scan_meta(self, filename: Path) -> Iterable[Path]:
        buffer = ''
        state = 'scan'
        for line in filename.read_text().splitlines():
            if state == 'scan':
                match = self._IMPORT_PATTERN.match(line)
                if match:
                    buffer += match.group(1) + ' '
                    state = 'more'

            elif state == 'more':
                match = self._ADDITIONAL_PATTERN.match(line)
                if match:
                    buffer += match.group(1) + ' '
                else:  # No match
                    break  # We are done
        return [Path(path) for path in buffer.split()]

    def ready(self) -> bool:
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
                    test_name = root / head / 'rose-meta.conf'
                    mp_get_logger().debug(f"Possible ({test_name.exists()}): {test_name}")
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


# Todo: Get new starters to make clean-room implementation of meta file parser
#       so we can stop using "rose picker."
#
class RosePicker(Action):
    def __init__(self, filename: Path, core_dir: Path,
                 database: Database):
        self._filename = filename
        self._core_dir = core_dir
        self._database = database

    def __str__(self) -> str:
        return f"Rose picking: {self._filename.name}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [RosePickerPrerequisite(self._filename, self._database)]

    def perform(self) -> Iterable[Action | ActionResult]:
        configuration_dir = self._database.configuration.build_dir / 'configuration'
        configuration_dir.mkdir(parents=True, exist_ok=True)
        command = ['rose_picker', str(self._filename),
                   '-directory', str(configuration_dir)]
        for directory in self._database.config_meta_dirs:
            command.extend(['-include_dirs', str(directory)])
        process = run(command, stdout=PIPE, stderr=PIPE, encoding='utf8')
        if process.returncode != 0:
            return [ActionResult(self, process.returncode, ' '.join(command),
                                 process.stdout, process.stderr)]

        return [
            ConfigurationLoader(configuration_dir / 'config_namelists.txt',
                                self._core_dir, self._database),
            NamelistLoader(configuration_dir / 'rose-meta.json',
                           configuration_dir / 'config_namelists.txt',
                           self._core_dir, self._database)
        ]


class ConfigurationLoader(Action):
    def __init__(self, filename: Path, core_dir: Path, database: Database):
        self._filename = filename
        self._core_dir = core_dir
        self._database = database

    def __str__(self) -> str:
        return f"Configuration loader: {self._filename}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self._filename)]

    def perform(self) -> Iterable[Action | ActionResult]:
        source_file = (self._database.configuration.build_dir
                       / 'configuration' / 'configuration_mod.f90')

        command = [str(self._core_dir / 'infrastructure' / 'build' / 'tools' / 'GenerateLoader'),
                   str(source_file)]
        for line in self._filename.read_text().splitlines():
            for namelist in line.split():
                command.append(namelist)
        run(command, check=True)

        return [AnalyseFortran(source_file, self._database)]


# Todo: Change namelist generation to be done namelist at a time.
#
class NamelistLoader(Action):
    def __init__(self, json_file: Path, namelist_file: Path, core_dir: Path,
                 database: Database):
        self._json_file = json_file
        self._namelist_file = namelist_file
        self._core_dir = core_dir
        self._database = database

    def __str__(self) -> str:
        return f"Namelist loader: {self._json_file}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self._json_file),
                FilePrerequisite(self._namelist_file)]

    def perform(self) -> Iterable[Action | ActionResult]:
        actions: list[Action | ActionResult] = []

        config_dir = self._database.configuration.build_dir / 'configuration'
        command = [str(self._core_dir / 'infrastructure' / 'build' / 'tools' / 'GenerateNamelist'),
                   str(self._json_file),
                   '-directory', str(config_dir)]
        process = run(command, stdout=PIPE, stderr=PIPE, encoding='utf8')
        if process.returncode != 0:
            actions.append(ActionResult(self,
                                        process.returncode,
                                        ' '.join(command),
                                        process.stdout,
                                        process.stderr))

        for line in self._namelist_file.read_text().splitlines():
            for namelist in line.split():
                leafname = namelist + '_config_mod.f90'
                actions.append(
                    AnalyseFortran(config_dir / leafname, self._database)
                )
        return actions
