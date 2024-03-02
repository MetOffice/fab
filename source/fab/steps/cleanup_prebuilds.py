# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Pruning of old files from the incremental/prebuild folder.

"""
import logging
import os
from datetime import timedelta, datetime
from pathlib import Path
from typing import Dict, Optional, Iterable, Set

from fab.constants import CURRENT_PREBUILDS
from fab.steps import run_mp, step
from fab.util import file_walk, get_prebuild_file_groups

logger = logging.getLogger(__name__)


CLEANUP_COUNT = 'cleanup_count'


@step
def cleanup_prebuilds(
        config, older_than: Optional[timedelta] = None, n_versions: int = 0, all_unused: Optional[bool] = None):
    """
    A step to delete old files from the local incremental/prebuild folder.

    Assumes prebuild filenames follow the pattern: `<stem>.<hash>.<suffix>`.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read settings
        such as the project workspace folder or the multiprocessing flag.
    :param older_than:
        Delete prebuild artefacts which are *n seconds* older than the *last prebuild access time*.
    :param n_versions:
        Only keep the most recent n versions of each artefact `<stem>.*.<suffix>`
    :param all_unused:
        Delete everything which was not part of the current build.

    If no parameters are specified then `all_unused` will default to `True`.

    """
    # If the user has not specified any cleanup parameters, we default to a hard cleanup.
    if not n_versions and not older_than:
        if all_unused not in [None, True]:
            raise ValueError(f"unexpected value for all_unused: '{all_unused}'")
        all_unused = True

    # if we're doing a hard cleanup, there's no point providing the softer options
    if all_unused and (n_versions or older_than):
        raise ValueError("n_versions or older_than should not be specified with all_unused")

    num_removed = 0

    # see what's in the prebuild folder
    prebuild_files = list(file_walk(config.prebuild_folder))
    if not prebuild_files:
        logger.info('no prebuild files found')

    elif all_unused:
        num_removed = remove_all_unused(
            found_files=prebuild_files, current_files=config.artefact_store[CURRENT_PREBUILDS])

    else:
        # get the file access time for every artefact
        prebuilds_ts = \
            dict(zip(prebuild_files, run_mp(config, prebuild_files, get_access_time)))  # type: ignore

        # work out what to delete
        to_delete = by_age(older_than, prebuilds_ts, current_files=config.artefact_store[CURRENT_PREBUILDS])
        to_delete |= by_version_age(n_versions, prebuilds_ts, current_files=config.artefact_store[CURRENT_PREBUILDS])

        # delete them all
        run_mp(config, to_delete, os.remove)
        num_removed = len(to_delete)

    logger.info(f'removed {num_removed} prebuild files')
    config.artefact_store[CLEANUP_COUNT] = num_removed


def by_age(older_than: Optional[timedelta],
           prebuilds_ts: Dict[Path, datetime], current_files: Iterable[Path]) -> Set[Path]:
    to_delete = set()

    if older_than:
        most_recent_ts = max(prebuilds_ts.values())
        oldest_ts_allowed = most_recent_ts - older_than

        for f, ts in prebuilds_ts.items():
            if ts < oldest_ts_allowed:
                # don't delete if it's still current
                if f in current_files:
                    logger.debug(f"old file is still current {f}")
                    continue
                logger.info(f"old file {f}")
                to_delete.add(f)

    return to_delete


def by_version_age(n_versions: int, prebuilds_ts: Dict[Path, datetime], current_files: Iterable[Path]) -> Set[Path]:
    to_delete = set()

    if n_versions:
        # group prebuild files by originating artefact, <stem>.*.<suffix>
        pb_file_groups = get_prebuild_file_groups(prebuilds_ts.keys())

        # delete the n oldest in each group
        for pb_group in pb_file_groups.values():
            by_age = sorted(pb_group, key=lambda f: prebuilds_ts[f], reverse=True)
            for f in by_age[n_versions:]:
                # don't delete if it's still current
                if f in current_files:
                    logger.debug(f"old version is still current {f}")
                    continue
                logger.debug(f"old version {f}")
                to_delete.add(f)

    return to_delete


def remove_all_unused(found_files: Iterable[Path], current_files: Iterable[Path]):
    num_removed = 0

    for f in found_files:
        if f not in current_files:
            logger.info(f"unused {f}")
            os.remove(f)
            num_removed += 1

    return num_removed


def get_access_time(fpath: Path) -> datetime:
    """
    Return the access time of the given file.

    Depends on the file system's ability to report a file's last access time
    via the `os.stat_result.st_atime` returned by `Path.stat`.

    """
    ts = fpath.stat().st_atime
    return datetime.fromtimestamp(ts)
