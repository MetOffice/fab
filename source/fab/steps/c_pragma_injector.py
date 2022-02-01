"""
Add custom pragmas to C code which identify user and system include regions.

"""
from pathlib import Path
from typing import Dict, Iterable

from fab.steps import Step
from fab.tasks.c import _CTextReaderPragmas
from fab.util import suffix_filter


class CPragmaInjector(Step):

    def __init__(self, input_name="all_source", output_name="pragmad_c", input_suffixes=None, name="c pragmas"):
        super().__init__(name=name)

        self.input_name = input_name
        self.output_name = output_name
        self.input_suffixes: Iterable[str] = input_suffixes or ['.c']

    def run(self, artefacts: Dict):
        """
        By default, reads .c files from the *all_source* artefact and creates the *pragmad_c* artefact.

        """
        files: Iterable[Path] = suffix_filter(artefacts[self.input_name], self.input_suffixes)
        results = self.run_mp(items=files, func=self._process_artefact)
        artefacts[self.output_name] = list(results)

    def _process_artefact(self, fpath: Path):
        prag_output_fpath = fpath.with_suffix('.prag')
        prag_output_fpath.open('w').writelines(_CTextReaderPragmas(fpath))
