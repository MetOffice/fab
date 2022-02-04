"""
Gather files from a source folder.

"""
from pathlib import Path
from typing import Optional

from fab.constants import BUILD_OUTPUT

from fab.steps import Step
from fab.util import file_walk

import logging

logger = logging.getLogger('fab')


class WalkSource(Step):

    def __init__(self,
                 build_source: Path, output_name="all_source",
                 build_output: Optional[Path]=None, name="walk source"):
        super().__init__(name)
        self.build_source = build_source
        self.output_artefact = output_name
        self.build_output = build_output or build_source.parent / BUILD_OUTPUT

    def run(self, artefacts, config):
        """
        Get all files in the folder and subfolders.

        Requires no artefacts, creates the "all_source" artefact.

        """
        super().run(artefacts, config)

        fpaths = list(file_walk(self.build_source))
        if not fpaths:
            raise RuntimeError(f"no source files found")

        # todo: separate step?
        # create output folders
        input_folders = set()
        for fpath in fpaths:
            input_folders.add(fpath.parent.relative_to(self.build_source))
        for input_folder in input_folders:
            path = self.build_output / input_folder
            path.mkdir(parents=True, exist_ok=True)

        artefacts[self.output_artefact] = fpaths
