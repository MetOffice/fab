##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Gather files from a source folder.

"""
import logging
from typing import Optional, Iterable

from fab.steps import Step
from fab.util import file_walk

logger = logging.getLogger(__name__)


class _PathFilter(object):
    # Simple pattern matching using string containment check.
    # Deems an incoming path as included or excluded.

    def __init__(self, *filter_strings: str, include: bool):
        """
        :param filter_strings:
            One or more strings to be used as pattern matches.
        :param include:
            Set to True or False to include or exclude matching paths.

        """
        self.filter_strings: Iterable[str] = filter_strings
        self.include = include

    def check(self, path):
        if any(str(i) in str(path) for i in self.filter_strings):
            return self.include
        return None


class Include(_PathFilter):
    """
    A path filter which includes matching paths, this convenience class improves config readability.

    """
    def __init__(self, *filter_strings):
        """
        :param filter_strings:
            One or more strings to be used as pattern matches.

        """
        super().__init__(*filter_strings, include=True)

    def __str__(self):
        return f'Include({", ".join(self.filter_strings)})'


class Exclude(_PathFilter):
    """
    A path filter which excludes matching paths, this convenience class improves config readability.

    """

    def __init__(self, *filter_strings):
        """
        :param filter_strings:
            One or more strings to be used as pattern matches.

        """
        super().__init__(*filter_strings, include=False)

    def __str__(self):
        return f'Exclude({", ".join(self.filter_strings)})'


class FindSourceFiles(Step):
    """
    Find the files in the source folder, with filtering.

    Files can be included or excluded with simple pattern matching.
    Every file is included by default, unless the filters say otherwise.

    Path filters are expected to be provided by the user in an *ordered* collection.
    The two convenience subclasses, :class:`~fab.steps.walk_source.Include` and :class:`~fab.steps.walk_source.Exclude`,
    improve readability.

    Order matters. For example::

        path_filters = [
            Exclude('my_folder'),
            Include('my_folder/my_file.F90'),
        ]

    In the above example, swapping the order would stop the file being included in the build.

    A path matches a filter string simply if it *contains* it,
    so the path *my_folder/my_file.F90* would match filters "my_folder", "my_file" and "er/my".

    """
    def __init__(self, source_root=None, output_collection="all_source",
                 name="Walk source", path_filters: Optional[Iterable[_PathFilter]] = None):
        """
        :param source_root:
            Optional path to source folder, with a sensible default.
        :param output_collection:
            Name of artefact collection to create, with a sensible default.
        :param path_filters:
            Iterable of Include and/or Exclude objects, to be processed in order.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(name)
        self.source_root = source_root
        self.output_collection: str = output_collection
        self.path_filters: Iterable[_PathFilter] = path_filters or []

    def run(self, artefact_store, config):
        """
        Recursively get all files in the given folder, with filtering.

        :param artefact_store:
            Contains artefacts created by previous Steps, and where we add our new artefacts.
            This is where the given :class:`~fab.artefacts.ArtefactsGetter` finds the artefacts to process.
        :param config:
            The :class:`fab.build_config.BuildConfig` object where we can read settings
            such as the project workspace folder or the multiprocessing flag.

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
