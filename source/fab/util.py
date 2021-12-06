import logging
import sys
import zlib
from collections import namedtuple, defaultdict
from pathlib import Path
from typing import Iterator, Dict, List


def log_or_dot(logger, msg):
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(msg)
    elif logger.isEnabledFor(logging.INFO):
        print('.', end='')
        # sys.stdout.flush()


def log_or_dot_finish(logger):
    if logger.isEnabledFor(logging.INFO):
        print('')


HashedFile = namedtuple("HashedFile", ['fpath', 'hash'])


def do_checksum(fpath: Path):
    with open(fpath, "rb") as infile:
        return HashedFile(fpath, zlib.crc32(bytes(infile.read())))


def file_walk(path: Path, skip_files=None, logger=None) -> Iterator[Path]:
    skip_files = skip_files or []
    assert path.is_dir()

    for i in path.iterdir():
        if i.is_dir():
            yield from file_walk(i, skip_files=skip_files, logger=logger)
        else:
            if i.parts[-1] in skip_files:
                if logger:
                    logger.debug(f"skipping {i}")
                continue
            yield i


def get_fpaths_by_type(fpaths: Iterator[Path]) -> Dict[str, List]:
    """
    Group a list of paths according to their extensions.

    We use sorted lists instead of a sets for repeatable output which is easier to scan.
    """

    fpaths_by_type = defaultdict(list)
    for fpath in fpaths:
        fpaths_by_type[fpath.suffix].append(fpath)

    # sort for repeatable output which is easier to scan
    # we might eventually sort hefty tasks to the front
    for key in fpaths_by_type:
        fpaths_by_type[key] = sorted(fpaths_by_type[key])

    return fpaths_by_type

