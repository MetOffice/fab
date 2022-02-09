"""
Add custom pragmas to C code which identify user and system include regions.

"""
from pathlib import Path
from typing import Dict

from fab.steps import Step
from fab.tasks.c import _CTextReaderPragmas
from fab.util import SourceGetter, FilterFpaths

DEFAULT_SOURCE_GETTER = FilterFpaths('all_source', ['.c'])


# todo: test
class CPragmaInjector(Step):

    def __init__(self, source: SourceGetter = None, output_name="pragmad_c", name="c pragmas"):
        super().__init__(name=name)

        self.source_getter = source or DEFAULT_SOURCE_GETTER
        self.output_name = output_name

    def run(self, artefacts: Dict, config):
        """
        By default, reads .c files from the *all_source* artefact and creates the *pragmad_c* artefact.

        """
        super().run(artefacts, config)

        files = self.source_getter(artefacts)
        results = self.run_mp(items=files, func=self._process_artefact)
        artefacts[self.output_name] = list(results)

    def _process_artefact(self, fpath: Path):
        prag_output_fpath = fpath.with_suffix('.prag')
        prag_output_fpath.open('w').writelines(_CTextReaderPragmas(fpath))
        return prag_output_fpath
