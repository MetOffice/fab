##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Object archive (.a) creation from a list of object files (.o) for use in static linking.

"""

import logging
from string import Template
from typing import List, Dict

from fab.constants import BUILD_OUTPUT
from fab.steps import Step
from fab.util import CompiledFile, log_or_dot, run_command
from fab.artefacts import ArtefactGetterBase, ArtefactConcat

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = ArtefactConcat(['compiled_c', 'compiled_fortran'])


class ArchiveObjects(Step):

    def __init__(self, source: ArtefactGetterBase = None, archiver='ar',
                 output_fpath='output.a', name='archive objects'):
        """
        Kwargs:
            - archiver: The archiver executable. Defaults to 'ar'.
            - output_fpath: The file path of the output archive file.

        """
        super().__init__(name)

        self.source_getter = source or DEFAULT_SOURCE_GETTER
        self.archiver = archiver
        self.output_fpath = output_fpath

    def run(self, artefact_store: Dict, config):
        """
        Creates an object archive from the all the object files in the artefact store.

        By default, it finds the object files under the labels *compiled_c* and *compiled_fortran*.

        """
        super().run(artefact_store, config)

        compiled_files: List[CompiledFile] = self.source_getter(artefact_store)

        command = [self.archiver]
        command.extend(['cr', Template(self.output_fpath).substitute(output=config.workspace / BUILD_OUTPUT)])
        command.extend([str(a.output_fpath) for a in compiled_files])

        log_or_dot(logger, 'CreateObjectArchive running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error creating object archive: {err}")

        return self.output_fpath
