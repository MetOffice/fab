import logging
from typing import List

from fab.steps import Step
from fab.util import CompiledFile, log_or_dot, run_command


logger = logging.getLogger('fab')


class LinkExe(Step):
    """
    A build step to produce an executable from a list of object (.o) files.

    """
    def __init__(self, linker: str, flags: List[str], output_fpath: str, name='link exe'):
        """
        Args:
            - linker: E.g 'gcc' or 'ld'.
            - flags: A list of flags to pass to the linker.
            - output_fpath: The file path of the output exe.

        """
        super().__init__(name)
        self.linker = linker
        self.flags = flags
        self.output_fpath = output_fpath

    def run(self, artefacts):

        compiled_files = artefacts['compiled_c'] + artefacts['compiled_fortran']

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
