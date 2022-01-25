from collections import defaultdict
from pathlib import Path
from typing import Optional

from fab.constants import BUILD_OUTPUT

from fab.steps import Step
from fab.util import file_walk

import logging

logger = logging.getLogger('fab')


class WalkSource(Step):

    def __init__(self, build_source: Path, build_output: Optional[Path]=None, name="walk source"):
        super().__init__(name)
        self.build_source = build_source
        self.build_output = build_output or build_source.parent / BUILD_OUTPUT

    def run(self, artefacts):
        """
        Get all files in the folder and subfolders.

        Returns a dict[source_folder][extension] = file_list

        """
        fpaths = file_walk(self.build_source)
        if not fpaths:
            logger.warning(f"no source files found")
            exit(1)

        # group files by suffix, and note the folders so we can create the output folder structure in advance
        fpaths_by_type = defaultdict(list)
        input_folders = set()
        for fpath in fpaths:
            fpaths_by_type[fpath.suffix].append(fpath)
            input_folders.add(fpath.parent.relative_to(self.build_source))

        # create output folders
        for input_folder in input_folders:
            path = self.build_output / input_folder
            path.mkdir(parents=True, exist_ok=True)

        artefacts["all_source"] = fpaths_by_type


    # def input_artefacts(self, artefacts):
    #     pass
    #
    # def process_artefact(self, artefact):
    #     pass
    #
    # def output_artefacts(self, results, artefacts):
    #     pass

