##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
import re
import subprocess
import sys
import zlib
from collections import namedtuple
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Iterator, Iterable

from fab.constants import BUILD_OUTPUT, SOURCE_ROOT

logger = logging.getLogger(__name__)


def log_or_dot(logger, msg):
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(msg)
    elif logger.isEnabledFor(logging.INFO):
        print('.', end='')
        sys.stdout.flush()


def log_or_dot_finish(logger):
    if logger.isEnabledFor(logging.INFO):
        print('')


HashedFile = namedtuple("HashedFile", ['fpath', 'file_hash'])


def do_checksum(fpath: Path):
    with open(fpath, "rb") as infile:
        return HashedFile(fpath, zlib.crc32(bytes(infile.read())))


def file_walk(path: Path) -> Iterator[Path]:
    assert path.is_dir(), f"not dir: '{path}'"
    for i in path.iterdir():
        if i.is_dir():
            yield from file_walk(i)
        else:
            yield i


@contextmanager
def time_logger(label):
    logger.info("\n" + label)
    start = perf_counter()
    yield None
    logger.info(f"{label} took {perf_counter() - start}")


# todo: better as a named tuple?
class CompiledFile(object):
    def __init__(self, analysed_file, output_fpath):
        self.analysed_file = analysed_file
        self.output_fpath = output_fpath


def input_to_output_fpath(workspace: Path, input_path: Path):
    rel_path = input_path.relative_to(workspace / SOURCE_ROOT)
    return workspace / BUILD_OUTPUT / rel_path


def case_insensitive_replace(in_str: str, find: str, replace_with: str):
    compiled_re = re.compile(find, re.IGNORECASE)
    return compiled_re.sub(replace_with, in_str)


def run_command(command):
    logger.debug(f'run_command: {command}')
    res = subprocess.run(command, capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed:\n{command}\n{res.stderr.decode()}")


def suffix_filter(fpaths: Iterable[Path], suffixes: Iterable[str]):
    """
    Pull out all the paths with a given suffix from an iterable.

    Args:
        - fpaths: Iterable of paths.
        - suffixes: Iterable of suffixes we want.

    """
    # todo: Just return the iterator from filter. Let the caller decide whether to turn into a list.
    return list(filter(lambda fpath: fpath.suffix in suffixes, fpaths))
