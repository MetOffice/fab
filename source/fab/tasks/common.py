# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution

import logging
import subprocess
from typing import List, Set
from pathlib import Path

from fab.constants import BUILD_SOURCE

from fab.config_sketch import FlagsConfig
from fab.tasks.c import _CTextReaderPragmas

from fab.util import CompiledFile, input_to_output_fpath, log_or_dot, fixup_command_includes, run_command


logger = logging.getLogger('fab')


class LinkExe(object):
    def __init__(self, linker, flags, output_filename):
        self.linker = linker
        self.flags = flags
        self.output_fpath = output_filename

    def run(self, compiled_files: List[CompiledFile]):
        command = [self.linker]
        command.extend(['-o', str(self.output_fpath)])
        command.extend([str(a.output_fpath) for a in compiled_files])
        # todo: why must this come after the list of object files?
        command.extend(self.flags)

        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error linking: {err}")

        return self.output_fpath


class CreateObjectArchive(object):
    def __init__(self, archiver, flags, output_fpath):
        self.archiver = archiver
        self.flags = flags
        self.output_fpath = output_fpath

    def run(self, compiled_files: List[CompiledFile]):
        command = [self.archiver]
        command.extend(['cr', self.output_fpath])
        command.extend([str(a.output_fpath) for a in compiled_files])

        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error creating object archive: {err}")

        return self.output_fpath


# def link_shared_object(compiled_files, linker, flags, output_fpath):
#     command = [linker]
#     command.extend(['-fPIC', '-shared', '-o', output_fpath])
#     command.extend([str(a.output_fpath) for a in compiled_files])
#
#     try:
#         run_command(command)
#     except Exception as err:
#         raise Exception(f"error linking: {err}")
#
#     return "foo"




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