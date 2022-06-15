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
from typing import Optional, Iterable

from fab.steps import Step
from fab.util import file_walk

logger = logging.getLogger(__name__)


class PathFilter(object):
    def __init__(self, *filter_strings: str, include: bool):
        self.filter_strings: Iterable[str] = filter_strings
        self.include = include

    def check(self, path):
        if any(str(i) in str(path) for i in self.filter_strings):
            return self.include
        return None


class Include(PathFilter):
    def __init__(self, *filter_strings):
        super().__init__(*filter_strings, include=True)

    def __str__(self):
        return f'Include({", ".join(self.filter_strings)})'


class Exclude(PathFilter):
    def __init__(self, *filter_strings):
        super().__init__(*filter_strings, include=False)

    def __str__(self):
        return f'Exclude({", ".join(self.filter_strings)})'


class FindSourceFiles(Step):
    """
    :param source_root:
        Path to source folder.
    :param output_collection:
        Name of artefact collection to create, defaults to "all_source".
    :param build_output:
        (Deprecated) where to create the output folders.
    :param path_filters:
        Iterable of PathFilter.
        Processed in order, if a source file matches the pattern it will be included or excluded,
        as per the bool.

    """

    def __init__(self,
                 source_root=None, output_collection="all_source",
                 build_output: Optional[Path] = None, name="Walk source",
                 path_filters: Optional[Iterable[PathFilter]] = None):
        super().__init__(name)
        self.source_root = source_root
        self.output_collection: str = output_collection
        self.build_output = build_output
        self.path_filters: Iterable[PathFilter] = path_filters or []

    def run(self, artefact_store, config):
        """
        Recursively get all files in the given folder.

        Requires no input artefact_store. By default, creates the "all_source" label in the artefacts.

        """
        super().run(artefact_store, config)

        source_root = self.source_root or config.source_root

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

        artefact_store[self.output_collection] = filtered_fpaths
