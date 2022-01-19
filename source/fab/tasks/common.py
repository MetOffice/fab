# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution

import logging
import subprocess
from typing import List, Set
from pathlib import Path

from fab.config_sketch import FlagsConfig
from fab.tasks.c import _CTextReaderPragmas

from fab.util import CompiledFile, input_to_output_fpath, log_or_dot, fixup_command_includes


class Linker(object):
    def __init__(self, linker: str, flags: List[str], workspace: Path, output_filename: str):
        self._linker = linker
        self._flags = flags
        self._workspace = workspace
        self._output_filename = output_filename

    def run(self, compiled_files: Set[CompiledFile]):
        logger = logging.getLogger(__name__)
        output_file = str(self._workspace / self._output_filename)

        # building a library?
        # shared object
        # todo: refactor this
        # TODO: WE PROBABLY WANT TO BUILD A .a FILE WITH ar INSTEAD OF A SHARED OBJECT - DISCUSS
        if self._output_filename.endswith('.so'):
            command = ['gcc', '-fPIC', '-shared', '-o', output_file]
            command.extend([str(a.output_fpath) for a in compiled_files])

        if self._output_filename.endswith('.a'):
            command = ['ar', 'cr', output_file]
            command.extend([str(a.output_fpath) for a in compiled_files])

        # building an executable
        else:
            command = [self._linker]
            command.extend(['-o', str(output_file)])
            for compiled_file in compiled_files:
                command.append(str(compiled_file.output_fpath))
            command.extend(self._flags)

        logger.debug('Running command: ' + ' '.join(command))

        try:
            res = subprocess.run(command, check=True)
            if res.returncode != 0:
                # todo: specific exception
                raise Exception(f"The command exited with non zero: {res.stderr.decode()}")
        except Exception as err:
            raise Exception(f"error: {err}")

        return self._output_filename


class PreProcessor(object):
    """Used for both C and Fortran"""

    def __init__(self,
                 preprocessor: List[str],
                 flags: FlagsConfig,
                 workspace: Path,
                 output_suffix=".c",  # but is also used for fortran
                 debug_skip=False,
                 ):
        self._preprocessor = preprocessor
        self._flags = flags
        self._workspace = workspace
        self.output_suffix = output_suffix
        self.debug_skip = debug_skip

    def run(self, fpath: Path):
        logger = logging.getLogger(__name__)

        output_fpath = input_to_output_fpath(workspace=self._workspace, input_path=fpath)

        if fpath.suffix == ".c":
            # pragma injection
            prag_output_fpath = fpath.parent / (fpath.name + ".prag")
            prag_output_fpath.open('w').writelines(_CTextReaderPragmas(fpath))
            input_fpath = prag_output_fpath
        elif fpath.suffix in [".f90", ".F90"]:
            input_fpath = fpath
            output_fpath = output_fpath.with_suffix('.f90')
        else:
            raise ValueError(f"Unexpected file type: '{str(fpath)}'")

        # for dev speed, but this could become a good time saver with, e.g, hashes or something
        if self.debug_skip and output_fpath.exists():
            log_or_dot(logger, f'Preprocessor skipping: {fpath}')
            return output_fpath

        if not output_fpath.parent.exists():
            output_fpath.parent.mkdir(parents=True, exist_ok=True)

        command = [*self._preprocessor]
        command.extend(self._flags.flags_for_path(fpath))

        # the flags we were given might contain include folders which need to be converted into absolute paths
        # todo: inconsistent with the compiler (and c?), which doesn't do this - discuss
        fixup_command_includes(command=command, source_root=self._workspace / BUILD_SOURCE, file_path=fpath)

        # input and output files
        command.append(str(input_fpath))
        command.append(str(output_fpath))

        log_or_dot(logger, 'Preprocessor running command: ' + ' '.join(command))
        try:
            subprocess.run(command, check=True, capture_output=True)
        except subprocess.CalledProcessError as err:
            return Exception(f"Error running preprocessor command: {command}\n{err.stderr}")

        return output_fpath