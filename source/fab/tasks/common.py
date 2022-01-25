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
    """
    A build step to produce an executable from a list of object (.o) files.

    """
    def __init__(self, linker: str, flags: List[str], output_fpath: str):
        """
        Args:
            - linker: E.g 'gcc' or 'ld'.
            - flags: A list of flags to pass to the linker.
            - output_fpath: The file path of the output exe.

        """
        self.linker = linker
        self.flags = flags
        self.output_fpath = output_fpath

    def run(self, compiled_files: List[CompiledFile]):
        command = [self.linker]
        command.extend(['-o', str(self.output_fpath)])
        command.extend([str(a.output_fpath) for a in compiled_files])
        # todo: why must this come after the list of object files?
        command.extend(self.flags)

        log_or_dot(logger, 'LinkExe running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error linking: {err}")

        return self.output_fpath


class CreateObjectArchive(object):
    """
    A build step which creates an object archive from a list of object (.o) files.

    """
    def __init__(self, archiver='ar', output_fpath='output.a'):
        """
        Kwargs:
            - archiver: The archiver executable. Defaults to 'ar'.
            - output_fpath: The file path of the output archive file.

        """
        self.archiver = archiver
        self.output_fpath = output_fpath

    def run(self, compiled_files: List[CompiledFile]):
        command = [self.archiver]
        command.extend(['cr', self.output_fpath])
        command.extend([str(a.output_fpath) for a in compiled_files])

        log_or_dot(logger, 'CreateObjectArchive running command: ' + ' '.join(command))
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


# class PreProcessor(object):
#     """
#     A build step which calls a preprocessor. Used for both C and Fortran.
#
#     """
#
#     def __init__(self,
#                  flags: FlagsConfig,
#                  workspace: Path,
#                  preprocessor='cpp',
#                  debug_skip=False,
#                  ):
#         """
#         Args:
#             - flags: Config object defining common and per-path flags.
#             - workspace: The folder in which to find the source and output folders.
#
#         Kwargs:
#             - preprocessor: The name of the executable. Defaults to 'cpp'.
#             - debug_skip: Ignore this for now!
#
#         """
#         self._preprocessor = preprocessor
#         self._flags = flags
#         self._workspace = workspace
#         self.debug_skip = debug_skip
#
#     def run(self, fpath: Path):
#         """
#         Expects an input file in the source folder.
#         Writes the output file to the output folder, with a lower case extension.
#
#         """
#         logger = logging.getLogger(__name__)
#
#         output_fpath = input_to_output_fpath(workspace=self._workspace, input_path=fpath)
#
#         if fpath.suffix == ".c":
#             # pragma injection
#             # todo: The .prag file should probably live in the output folder.
#             prag_output_fpath = fpath.parent / (fpath.name + ".prag")
#             prag_output_fpath.open('w').writelines(_CTextReaderPragmas(fpath))
#             input_fpath = prag_output_fpath
#         elif fpath.suffix in [".f90", ".F90"]:
#             input_fpath = fpath
#             output_fpath = output_fpath.with_suffix('.f90')
#         else:
#             raise ValueError(f"Unexpected file type: '{str(fpath)}'")
#
#         # for dev speed, but this could become a good time saver with, e.g, hashes or something
#         if self.debug_skip and output_fpath.exists():
#             log_or_dot(logger, f'Preprocessor skipping: {fpath}')
#             return output_fpath
#
#         if not output_fpath.parent.exists():
#             output_fpath.parent.mkdir(parents=True, exist_ok=True)
#
#         command = [self._preprocessor]
#         command.extend(self._flags.flags_for_path(fpath))
#
#         # the flags we were given might contain include folders which need to be converted into absolute paths
#         # todo: inconsistent with the compiler (and c?), which doesn't do this - discuss
#         command = fixup_command_includes(command=command, source_root=self._workspace / BUILD_SOURCE, file_path=fpath)
#
#         # input and output files
#         command.append(str(input_fpath))
#         command.append(str(output_fpath))
#
#         log_or_dot(logger, 'PreProcessor running command: ' + ' '.join(command))
#         try:
#             run_command(command)
#         except Exception as err:
#             raise Exception(f"error preprocessing {fpath}: {err}")
#
#         return output_fpath
