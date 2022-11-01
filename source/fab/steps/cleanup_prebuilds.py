# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Pruning of old files from the prebuild folder.

"""
import logging
import os
import time
from collections import defaultdict
from datetime import timedelta, datetime
from pathlib import Path
from time import sleep
from typing import Dict, Optional

from fab.constants import CURRENT_PREBUILDS
from fab.steps import Step
from fab.util import file_walk, get_fab_workspace

logger = logging.getLogger(__name__)


# todo: poor name? Perhaps PrebuildCleanup, CleanupPrebuilds, or just Cleanup or Housekeeping?
class CleanupPrebuilds(Step):
    """
    A step to delete old files from the local prebuild folder.

    Assumes prebuild filenames follow the pattern: `<stem>.<hash>.<suffix>`.

    """
    # todo: add <stem>.<hash>.<suffix> pattern to docs, probably refer to it in several places

    def __init__(self, n_versions: int = 0, older_than: timedelta = 0, all_unused: Optional[bool] = None):
        """
        :param n_versions:
            Only keep the most recent n versions of each prebuild file `<stem>.*.<suffix>`
        :param older_than:
            Delete prebuild artefacts which are *n seconds* older than the *last prebuild access time*.
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

            # get the file access time for every prebuild file
            prebuilds_ts = dict(zip(prebuild_files, self.run_mp(prebuild_files, get_access_time), strict=True))
            most_recent_ts = max(prebuilds_ts.values())

            # build a set of all old files to delete
            to_delete = set()

            # identify old files
            if self.older_than:
                oldest_ts_allowed = most_recent_ts - self.older_than
                for pbf, ts in prebuilds_ts.items():
                    if ts < oldest_ts_allowed:
                        logger.info(f"old age {pbf}")
                        to_delete.add(pbf)

            # identify old versions
            if self.n_versions:

                # group prebuild files by originating artefact, <stem>.*.<suffix>
                pb_file_groups = get_prebuild_file_groups(prebuild_files)

                # delete the n oldest in each group
                for pb_group in pb_file_groups.values():
                    by_age = sorted(pb_group, key=lambda pbf: prebuilds_ts[pbf], reverse=True)
                    for pbf in by_age[self.n_versions:]:
                        logger.info(f"old version {pbf}")
                        to_delete.add(pbf)

            # delete them all
            num_removed = len(to_delete)
            self.run_mp(to_delete, os.remove)

        logger.info(f'removed {num_removed} prebuild files')


def remove_all_unused(found_files, current_files):
    num_removed = 0

    for pbf in found_files:
        if pbf not in current_files:
            pbf.unlink()
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
    logger.info(delta)
    if delta == 0:
        logger.info('file system reporting access time with low resolution')

    fpath.unlink()
    return True


def get_access_time(fpath: Path) -> datetime:
    ts = fpath.stat().st_atime
    return datetime.fromtimestamp(ts)


def get_prebuild_file_groups(prebuild_files) -> Dict[str, set]:
    """
    Group prebuild filenames by originating artefact.

    Prebuild filenames have the form `<stem>.<hash>.<suffix>`.
    This function creates a dict with wildcard key `<stem>.*.<suffix>`
    with each entry mapping to a set of all matching prebuild files.

    Given the input files *my_mod.123.o* and *my_mod.456.o*,
    returns a dict {'my_mod.*.o': {'my_mod.123.o', 'my_mod.456.o}}

    """
    pbf_groups = defaultdict(set)

    for pbf in prebuild_files:
        stem_stem = pbf.stem.split('.')[0]  # stem returns <stem>.<hash>
        wildcard_key = pbf.parent / f'{stem_stem}.*{pbf.suffix}'
        pbf_groups[wildcard_key].add(pbf)

    return pbf_groups
