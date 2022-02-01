"""
Object archive (.a) creation from a list of object files (.o) for use in static linking.

"""

import logging
from typing import List, Dict

from fab.steps import Step
from fab.util import CompiledFile, log_or_dot, run_command


logger = logging.getLogger('fab')


class ArchiveObjects(Step):

    def __init__(self, archiver='ar', output_fpath='output.a', name='archive objects'):
        """
        Kwargs:
            - archiver: The archiver executable. Defaults to 'ar'.
            - output_fpath: The file path of the output archive file.

        """
        super().__init__(name)
        self.archiver = archiver
        self.output_fpath = output_fpath

    def run(self, artefacts: Dict):
        """
        Creates an archive object from the *compiled_files* artefact.

        (Current thinking) does not create an entry in the artefacts dict because the config which creates this step
        is responsible for managing which files are passed to the linker.

        """
        compiled_files: List[CompiledFile] = artefacts['compiled_files']

        command = [self.archiver]
        command.extend(['cr', self.output_fpath])
        command.extend([str(a.output_fpath) for a in compiled_files])

        log_or_dot(logger, 'CreateObjectArchive running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error creating object archive: {err}")

        return self.output_fpath
