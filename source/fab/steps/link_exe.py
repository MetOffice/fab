##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Link an executable.

"""
import logging
from string import Template
from typing import List

from fab.constants import BUILD_OUTPUT
from fab.steps import Step
from fab.util import log_or_dot, run_command
from fab.artefacts import ArtefactsGetter, CollectionConcat

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = CollectionConcat(['compiled_c', 'compiled_fortran'])


class LinkExe(Step):
    """
    A build step to produce an executable from a list of object (.o) files.

    """

    def __init__(self, linker: str, output_fpath: str, flags=None, source: ArtefactsGetter = None, name='link exe'):
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
        self.flags: List[str] = flags or []
        self.output_fpath: str = str(output_fpath)

    def run(self, artefact_store, config):
        """
        Links all the object files in the artefact_store.

        By default, it finds the object files under the labels *compiled_c* and *compiled_fortran*.

        """
        super().run(artefact_store, config)

        compiled_files = self.source_getter(artefact_store)

        command = self.linker.split()
        command.extend(['-o', Template(self.output_fpath).substitute(
            output=str(config.project_workspace / BUILD_OUTPUT))])
        command.extend([str(a.output_fpath) for a in compiled_files])
        # note: this must this come after the list of object files?
        command.extend(self.flags)

        log_or_dot(logger, 'Link running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error linking: {err}")

        return self.output_fpath


class LinkSharedObject(LinkExe):

    def __init__(self, linker: str, output_fpath: str, flags=None, source: ArtefactsGetter = None,
                 name='link shared object'):
        super().__init__(linker=linker, flags=flags, output_fpath=output_fpath, source=source, name=name)

        ensure_flags = ['-fPIC', '-shared']
        for f in ensure_flags:
            if f not in self.flags:
                self.flags.append(f)
