import logging
from typing import List

from fab.steps import Step
from fab.util import CompiledFile, log_or_dot, run_command


logger = logging.getLogger('fab')


class ArchiveObjects(Step):
    """
    A build step which creates an object archive from a list of object (.o) files.

    """
    def __init__(self, archiver='ar', output_fpath='output.a', name='archive objects'):
        """
        Kwargs:
            - archiver: The archiver executable. Defaults to 'ar'.
            - output_fpath: The file path of the output archive file.

        """
        super().__init__(name)
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
