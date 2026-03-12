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
from typing import Iterable, Optional, Union

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps import step
from fab.util import file_walk

logger = logging.getLogger(__name__)


class _PathFilter():
    """
    Simple pattern matching using string containment check.
    Deems an incoming path as included or excluded.
    """

    def __init__(self, *filter_strings: Union[str, Path], include: bool):
        """
        :param filter_strings:
            One or more strings to be used as pattern matches.
        :param include:
            Set to True or False to include or exclude matching paths.

        """
        # Convert paths to strings:
        self.filter_strings: Iterable[str] = [str(i) for i in filter_strings]
        self.include = include

    def check(self, path: Path) -> tuple[int, Optional[bool]]:
        """
        Checks if the specified path contains one of the filter strings.
        If so, it returns the length of the longest filter string
        and the value of self.include (i.e. if the file is supposed to
        be included or excluded). If no filter matches, it will return
        (-1, None)

        :param path: the path to check.

        :returns: a tuple consisting of maximum filter match length and
            self.include; or (-1, None) if no filter matches.
        """
        str_path = str(path)
        try:
            max_len = max(len(i) for i in self.filter_strings if i in str_path)
        except ValueError:
            # No pattern matches
            return (-1, None)
        return (max_len, self.include)


class Include(_PathFilter):
    """
    A path filter which includes matching paths, this convenience class
    improves config readability.

    """
    def __init__(self, *filter_strings: str):
        """
        :param filter_strings:
            One or more strings to be used as pattern matches.

        """
        super().__init__(*filter_strings, include=True)

    def __str__(self):
        return f'Include({", ".join(self.filter_strings)})'


class Exclude(_PathFilter):
    """
    A path filter which excludes matching paths, this convenience class
    improves config readability.

    """

    def __init__(self, *filter_strings: str):
        """
        :param filter_strings:
            One or more strings to be used as pattern matches.

        """
        super().__init__(*filter_strings, include=False)

    def __str__(self):
        return f'Exclude({", ".join(self.filter_strings)})'


@step
def find_source_files(
        config: BuildConfig,
        source_root: Optional[Path] = None,
        output_collection: Union[ArtefactSet,
                                 str] = ArtefactSet.INITIAL_SOURCE_FILES,
        path_filters: Optional[Iterable[_PathFilter]] = None) -> None:
    """
    Find the files in the source folder, with filtering.

    Files can be included or excluded with simple pattern matching.
    Every file is included by default, unless the filters say otherwise.

    Path filters are expected to be provided by the user in an *ordered*
    collection. The two convenience subclasses,
    :class:`~fab.steps.walk_source.Include` and
    :class:`~fab.steps.walk_source.Exclude`, improve readability.

    This function will use the longest match to determine if a file is to
    be excluded or included (in case of a tie the last matching filter
    will apply). For example::

        path_filters = [
            Exclude('some_folder'),
            Include('some_folder/my_file.F90'),
        ]

    In the above example, swapping the order would not affect that ``my_file.F90``
    will be included. But if the filters have the same length::

        path_filters = [
            Exclude('some_folder'),
            Include('my_file.F90'),
        ]

    Then the last matching filter applies, in the order specified above this
    means the file would be included. If the order of ``Exclude`` and
    ``Include`` is swapped, the file would be excluded.

    A path matches a filter string simply if it *contains* it,
    so the path ``my_folder/my_file.F90`` would match filters
    ``my_folder``, ``my_file`` and ``er/my``.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read
        settings such as the project workspace folder or the multiprocessing
        flag.
    :param source_root:
        Optional path to source folder, with a sensible default.
    :param output_collection:
        Name of artefact collection to create, with a sensible default.
    :param path_filters:
        Iterable of Include and/or Exclude objects, to be processed in order.
    :param name:
        Human friendly name for logger output, with sensible default.

    """
    path_filters = path_filters or []

    # Recursively get all files in the given folder, with filtering.

    source_root = source_root or config.source_root

    # file filtering
    filtered_fpaths = set()
    # todo: we shouldn't need to ignore the prebuild folder here, it's not
    # underneath the source root.
    for fpath in file_walk(source_root,
                           ignore_folders=[config.prebuild_folder]):
        # Search for the longest match (and latest one in case of
        # equal length)
        wanted = True
        max_len = -1
        for path_filter in path_filters:
            # did this filter have anything to say about this file?
            pattern_len, result = path_filter.check(fpath)
            if result is not None and pattern_len >= max_len:
                wanted = result
                max_len = pattern_len

        if wanted:
            filtered_fpaths.add(fpath)
        else:
            logger.debug(f"excluding {fpath}")

    if not filtered_fpaths:
        raise RuntimeError("no source files found after filtering")

    config.artefact_store.add(output_collection, filtered_fpaths)

    # Now split the files into the various main groups:
    # Fortran, C, and PSyclone
    config.artefact_store.copy_artefacts(output_collection,
                                         ArtefactSet.FORTRAN_COMPILER_FILES,
                                         suffixes=[".f", ".F", ".f90", ".F90"])

    config.artefact_store.copy_artefacts(output_collection,
                                         ArtefactSet.C_COMPILER_FILES,
                                         suffixes=[".c"])

    config.artefact_store.copy_artefacts(output_collection,
                                         ArtefactSet.X90_COMPILER_FILES,
                                         suffixes=[".x90", ".X90"])
