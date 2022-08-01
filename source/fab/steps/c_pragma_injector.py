##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Add custom pragmas to C code which identify user and system include regions.

"""
from pathlib import Path
from typing import Dict

from fab.steps import Step
from fab.tasks.c import CTextReaderPragmas
from fab.artefacts import ArtefactsGetter, SuffixFilter

DEFAULT_SOURCE_GETTER = SuffixFilter('all_source', '.c')


# todo: test
class CPragmaInjector(Step):
    """
    A build step to inject custom pragmas to mark blocks of user and system include statements.

    By default, reads .c files from the *all_source* artefact and creates the *pragmad_c* artefact.

    """
    def __init__(self, source: ArtefactsGetter = None, output_name="pragmad_c", name="c pragmas"):
        """
        :param source:
            An :class:`~fab.artefacts.ArtefactsGetter` which give us our c files to process.
        :param output_name:
            The name of the artefact collection to create in the artefact store, with a sensible default
        :param name:
            Human friendly name for logger output, with sensible default.
        """
        super().__init__(name=name)

        self.source_getter = source or DEFAULT_SOURCE_GETTER
        self.output_name = output_name

    def run(self, artefact_store: Dict, config):
        """
        :param artefact_store:
            Contains artefacts created by previous Steps, and where we add our new artefacts.
            This is where the given :class:`~fab.artefacts.ArtefactsGetter` finds the artefacts to process.
        :param config:
            The :class:`fab.build_config.BuildConfig` object where we can read settings
            such as the project workspace folder or the multiprocessing flag.

        """
        super().run(artefact_store, config)

        files = self.source_getter(artefact_store)
        results = self.run_mp(items=files, func=self._process_artefact)
        artefact_store[self.output_name] = list(results)

    def _process_artefact(self, fpath: Path):
        prag_output_fpath = fpath.with_suffix('.prag')
        prag_output_fpath.open('w').writelines(CTextReaderPragmas(fpath))
        return prag_output_fpath
