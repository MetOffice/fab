# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Pruning of old files from the prebuild folder.

"""
import logging
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from time import sleep
from typing import Dict

from fab.constants import CURRENT_PREBUILDS
from fab.steps import Step
from fab.util import file_walk, get_fab_workspace

logger = logging.getLogger(__name__)


class PrebuildPrune(Step):
    """
    Deletes files from the prebuild folder which meet certain conditions.

    Assumes prebuild filenames follow the pattern: <stem>.<hash>.<suffix>

    """
    # todo: add filename pattern to docs, probably refer to it in several places

    def __init__(self, n_versions=10, older_than=timedelta(days=30), all_unused=False):
        """
        :param n_versions:
            Only keep the most recent n prebuild versions of each file.
        :param older_than:
            Delete prebuild artefacts which are a given amount older *than the last access time* in the prebuild folder.
        :param all_unused:
            Delete everything which was not part of the current build.

        """
        super().__init__(name='prebuild prune')
        self.n_versions = n_versions
        self.older_than = older_than
        self.all_unused = all_unused

    def run(self, artefact_store: Dict, config):

        num_removed = 0

        # see what's in the prebuild folder
        prebuild_files = list(file_walk(config.prebuild_folder))
        if not prebuild_files:
            logger.info('no prebuild files found')

        elif self.all_unused:
            num_removed = self.remove_all_unused(prebuild_files, current_prebuilds=artefact_store[CURRENT_PREBUILDS])

        else:
            # Make sure the prebuild folder file system can give us access times
            assert check_fs_access_time(config.prebuild_folder), "file access time not available on this fs"

            # get the file access time for every artefact
            prebuilds_ts = dict(zip(prebuild_files, self.run_mp(prebuild_files, get_access_time), strict=True))

            if self.n_versions:
                # get the glob wildcard version for each file
                pb_file_groups = get_prebuild_file_groups(prebuild_files)
                for pb_group in pb_file_groups.values():
                    # sort this prebuild group by access time and remove the last n
                    sorted_group = sorted(pb_group, key=lambda pbf: prebuilds_ts[pbf], reverse=True)
                    for pbf in sorted_group[self.n_versions:]:
                        logger.info(f"removing old prebuild version {pbf}")
                        pbf.unlink()
                        num_removed += 1
                    raise NotImplementedError()

            if self.older_than:

                most_recent_ts = max(prebuilds_ts.values())
                oldest_ts_allowed = most_recent_ts - self.older_than

                for pbf, ts in prebuilds_ts:
                    if ts < oldest_ts_allowed:
                        logger.info(f"removing old prebuild file {pbf}")
                        pbf.unlink()
                        num_removed += 1

        logger.info(f'removed {num_removed} prebuild files')

    def remove_all_unused(self, prebuild_files, current_prebuilds):
        num_removed = 0

        # todo: we can't populate this until the prebuild prs are merged
        for pbf in prebuild_files:
            if pbf not in current_prebuilds:
                pbf.unlink()
                num_removed += 1
        raise NotImplementedError('fill in the artefact collection and test before review')

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

    # read the file and get the latest access time - this is not so important, should we bother?
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


def get_access_time(fpath: Path):
    return fpath.stat().st_atime_ns


def get_prebuild_file_groups(prebuild_files):
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
        key = pbf.parent / f'{stem_stem}.*{pbf.suffix}'
        pbf_groups[key].add(pbf)

    return pbf_groups
