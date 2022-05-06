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

from fab.build_config import PathFilter

from fab.constants import BUILD_OUTPUT
from fab.steps import Step
from fab.util import file_walk

logger = logging.getLogger(__name__)


INCLUDE = True
EXCLUDE = False


class FindSourceFiles(Step):

    def __init__(self,
                 source_root=None, output_collection="all_source",
                 build_output: Optional[Path] = None, name="Walk source",
                 file_filtering: Optional[List[Tuple]] = None):
        """
        Args:
            - source_root: Path to source folder.
            - output_collection: Name of artefact collection to create, defaults to "all_source".
            - build_output: (Deprecated) where to create the output folders.
            - file_filtering: List of (file pattern, boolean) tuples.
                    Processed in order, if a source file matches the pattern it will be included or excluded,
                    as per the bool.

        """
        super().__init__(name)
        self.source_root = source_root
        self.output_collection: str = output_collection
        self.build_output = build_output

        file_filtering = file_filtering or []
        self.path_filters: List[PathFilter] = [PathFilter(*i) for i in file_filtering]

    def run(self, artefact_store, config):
        """
        Recursively get all files in the given folder.

        Requires no input artefact_store. By default, creates the "all_source" label in the artefacts.

        """
        super().run(artefact_store, config)

        source_root = self.source_root or config.source_root
        build_output = self.build_output or source_root.parent / BUILD_OUTPUT

        # file filtering
        filtered_fpaths = []
        for fpath in file_walk(source_root):

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

        if not filtered_fpaths:
            raise RuntimeError("no source files found after filtering")

        # create output folders
        # todo: separate step for folder creation?
        input_folders = set()
        for fpath in filtered_fpaths:
            input_folders.add(fpath.parent.relative_to(source_root))
        for input_folder in input_folders:
            path = build_output / input_folder
            path.mkdir(parents=True, exist_ok=True)

        artefact_store[self.output_collection] = filtered_fpaths
