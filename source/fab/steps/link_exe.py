"""
Link an executable.

"""
import logging
from typing import List

from fab.steps import Step
from fab.util import log_or_dot, run_command, Artefacts, SourceGetter

logger = logging.getLogger('fab')


DEFAULT_SOURCE_GETTER = Artefacts(['compiled_c', 'compiled_fortran'])


class LinkExe(Step):
    """
    A build step to produce an executable from a list of object (.o) files.

    """
    def __init__(self, linker: str, flags: List[str], output_fpath: str, source: SourceGetter=None, name='link exe'):
        """
        Args:
            - linker: E.g 'gcc' or 'ld'.
            - flags: A list of flags to pass to the linker.
            - output_fpath: The file path of the output exe.
            - source:
            - name:

        """
        super().__init__(name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER
        self.linker = linker
        self.flags = flags
        self.output_fpath = output_fpath

    def run(self, artefacts, config):
        """
        Links all the object files in the *compiled_c* and *compiled_fortran* artefacts.

        (Current thinking) does not create an entry in the artefacts dict.

        """
        super().run(artefacts, config)

        compiled_files = self.source_getter(artefacts)

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
