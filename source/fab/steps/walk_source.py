##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Gather files from a source folder.

"""
import logging
from pathlib import Path
from typing import Optional, List, Tuple

from fab.config import PathFilter
from fab.constants import BUILD_OUTPUT
from fab.steps import Step
from fab.util import file_walk

logger = logging.getLogger('fab')


INCLUDE = True
EXCLUDE = False


class FindSourceFiles(Step):

    def __init__(self,
                 source_root: Path, output_name="all_source",
                 build_output: Optional[Path] = None, name="Walk source",
                 file_filtering: Optional[List[Tuple]] = None):
        """
        Args:
            - source_root: Path to source folder.
            - output_name: Name of artefact to create, defaults to "all_source".
            - build_output: (Deprecated) where to create the output folders.
            - file_filtering: List of (file pattern, boolean) tuples.
                    Processed in order, if a source file matches the pattern it will be included or excluded,
                    as per the bool.

        """
        super().__init__(name)
        self.source_root = source_root
        self.output_artefact = output_name
        self.build_output = build_output or source_root.parent / BUILD_OUTPUT

        file_filtering = file_filtering or []
        self.path_filters: List[PathFilter] = [PathFilter(*i) for i in file_filtering]

    def run(self, artefacts, config):
        """
        Get all files in the folder and subfolders.

        Requires no artefacts, creates the "all_source" artefact.

        """
        super().run(artefacts, config)

        fpaths = list(file_walk(self.source_root))
        if not fpaths:
            raise RuntimeError("no source files found")

        # file filtering
        filtered_fpaths = []
        for fpath in fpaths:

            wanted = True
            for path_filter in self.path_filters:
                # did this filter have anything to say about this file?
                res = path_filter.check(fpath)
                if res is not None:
                    wanted = res

            if wanted:
                filtered_fpaths.append(fpath)
            else:
                logger.debug(f"excluding {fpath}")

        # create output folders
        # todo: separate step for folder creation?
        input_folders = set()
        for fpath in filtered_fpaths:
            input_folders.add(fpath.parent.relative_to(self.source_root))
        for input_folder in input_folders:
            path = self.build_output / input_folder
            path.mkdir(parents=True, exist_ok=True)

        artefacts[self.output_artefact] = filtered_fpaths
