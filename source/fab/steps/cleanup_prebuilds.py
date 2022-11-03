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
import time
from datetime import timedelta, datetime
from pathlib import Path
from time import sleep
from typing import Dict, Optional, Iterable, Set

from fab.constants import CURRENT_PREBUILDS
from fab.steps import Step
from fab.util import file_walk, get_fab_workspace, get_prebuild_file_groups

logger = logging.getLogger(__name__)


# todo: poor name? Perhaps PrebuildCleanup, CleanupPrebuilds, or just Cleanup or Housekeeping?
class CleanupPrebuilds(Step):
    """
    A step to delete old files from the local incremental/prebuild folder.

    Assumes prebuild filenames follow the pattern: `<stem>.<hash>.<suffix>`.

    """
    # todo: add <stem>.<hash>.<suffix> pattern to docs, probably refer to it in several places

    def __init__(self, older_than: Optional[timedelta] = None, n_versions: int = 0, all_unused: Optional[bool] = None):
        """
        :param older_than:
            Delete prebuild artefacts which are *n seconds* older than the *last prebuild access time*.
        :param n_versions:
            Only keep the most recent n versions of each artefact `<stem>.*.<suffix>`
        :param all_unused:
            Delete everything which was not part of the current build.

        If no parameters are specified then `all_unused` will default to `True`.

        """
        super().__init__(name='cleanup prebuilds')

        self.n_versions = n_versions
        self.older_than = older_than
        self.all_unused = all_unused

        # If the user has not specified any cleanup parameters, we default to a hard cleanup.
        if not n_versions and not older_than:
            if all_unused not in [None, True]:
                raise ValueError(f"unexpected value for all_unused: '{all_unused}'")
            self.all_unused = True

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        num_removed = 0

        # see what's in the prebuild folder
        prebuild_files = list(file_walk(config.prebuild_folder))
        if not prebuild_files:
            logger.info('no prebuild files found')

        elif self.all_unused:
            num_removed = remove_all_unused(found_files=prebuild_files, current_files=artefact_store[CURRENT_PREBUILDS])

        else:
            # Make sure the file system can give us access times - overkill?
            if not check_fs_access_time(config.prebuild_folder):
                logger.error("file access time not available, aborting housekeeping")
                return

            # get the file access time for every artefact
            prebuilds_ts = dict(zip(prebuild_files, self.run_mp(prebuild_files, get_access_time), strict=True))

            # work out what to delete
            to_delete = self.by_age(prebuilds_ts, current_files=artefact_store[CURRENT_PREBUILDS])
            to_delete |= self.by_version_age(prebuilds_ts, current_files=artefact_store[CURRENT_PREBUILDS])

            # delete them all
            self.run_mp(to_delete, os.remove)
            num_removed = len(to_delete)

        logger.info(f'removed {num_removed} prebuild files')

    def by_age(self, prebuilds_ts: Dict[Path, datetime], current_files: Iterable[Path]) -> Set[Path]:
        to_delete = set()

        # todo: don't delete current artefacts, no matter how old they are
        xxx

        if self.older_than:
            most_recent_ts = max(prebuilds_ts.values())
            oldest_ts_allowed = most_recent_ts - self.older_than

            for pbf, ts in prebuilds_ts.items():
                if ts < oldest_ts_allowed:
                    logger.info(f"old file {pbf}")
                    to_delete.add(pbf)

        return to_delete

    def by_version_age(self, prebuilds_ts: Dict[Path, datetime], current_files: Iterable[Path]) -> Set[Path]:
        to_delete = set()

        # todo: don't delete current artefacts, no matter how old they are
        xxx

        if self.n_versions:
            # group prebuild files by originating artefact, <stem>.*.<suffix>
            pb_file_groups = get_prebuild_file_groups(prebuilds_ts.keys())

            # delete the n oldest in each group
            for pb_group in pb_file_groups.values():
                by_age = sorted(pb_group, key=lambda f: prebuilds_ts[f], reverse=True)
                for f in by_age[self.n_versions:]:
                    logger.info(f"old version {f}")
                    to_delete.add(f)

        return to_delete


def remove_all_unused(found_files: Iterable[Path], current_files: Iterable[Path]):
    num_removed = 0

    # logger.info(f'current artefacts:\n{current_files}\n')

    for f in found_files:
        if f not in current_files:
            logger.info(f"unused {f}")
            f.unlink()
            num_removed += 1

    return num_removed


# this whole function might be overkill...how likely is this, and do we care?
def check_fs_access_time(folder=None) -> bool:
    """
    Check if the file access time is recorded on this file system.

    Warn if it's low resolution, e.g. 1 day on FAT32.

    """
    folder = folder or get_fab_workspace()
    fpath = Path(folder) / f"_access_time_test{time.time_ns():x}.txt"
    fpath.parent.mkdir(parents=True, exist_ok=True)

    # create a file and get its access time
    fpath.unlink(missing_ok=True)
    open(fpath, 'wt').write("hello\n")
    write_time = fpath.stat().st_atime_ns
    try:
        int(write_time)
    except (ValueError, TypeError):
        logger.warning('file system does not report file access time')
        return False

    # read the file and get the updated access time - this is not so important, should we bother?
    sleep(0.1)
    open(fpath, "rt").readlines()
    read_time = fpath.stat().st_atime_ns

    # FAT32 has a 1 day resolution - not that we necessarily care...?
    delta = int(read_time) - int(write_time)
    if delta == 0:
        logger.info('file system reporting access time with low resolution')

    fpath.unlink()
    return True


def get_access_time(fpath: Path) -> datetime:
    ts = fpath.stat().st_atime
    return datetime.fromtimestamp(ts)
