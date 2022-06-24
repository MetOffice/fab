##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import datetime
import logging
import re
import subprocess
import sys
import zlib
from collections import namedtuple
from pathlib import Path
from time import perf_counter
from typing import Iterator, Iterable, Optional

from fab.constants import BUILD_OUTPUT

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


class Timer(object):
    """
    A simple timing context manager.
    """

    def __init__(self):
        self._start: Optional[float] = None
        self.taken: Optional[float] = None

    def __enter__(self):
        self._start = perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.taken = perf_counter() - self._start


class TimerLogger(Timer):
    """
    A labelled timing context manager which logs the label and the time taken.
    """

    def __init__(self, label, res=0.001):
        super().__init__()
        self.label = label
        self.res = res

    def __enter__(self):
        super().__enter__()
        logger.info("\n" + self.label)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)

        # log the time taken
        # don't bother reporting trivial timings
        seconds = int(self.taken / self.res) * self.res
        if seconds >= self.res:

            if seconds > 60:
                # convert to timedelta for human-friendly str()
                td = datetime.timedelta(seconds=seconds)
                logger.info(f"{self.label} took {td}")
            else:
                logger.info(f"{self.label} took {seconds:.3f}s")


class CompiledFile(object):
    def __init__(self, analysed_file, output_fpath):
        # todo: A compiled file shouldn't know whether its source file was analysed or not.
        #       It needn't be in some use cases.
        self.analysed_file = analysed_file
        self.output_fpath = output_fpath


def input_to_output_fpath(source_root: Path, project_workspace: Path, input_path: Path):
    build_output = project_workspace / BUILD_OUTPUT

    # perhaps it's already in the output folder? todo: can use Path.is_relative_to from Python 3.9
    try:
        input_path.relative_to(build_output)
        return input_path
    except ValueError:
        pass
    rel_path = input_path.relative_to(source_root)
    return build_output / rel_path


def case_insensitive_replace(in_str: str, find: str, replace_with: str):
    compiled_re = re.compile(find, re.IGNORECASE)
    return compiled_re.sub(replace_with, in_str)


def run_command(command, env=None):
    logger.debug(f'run_command: {command}')
    res = subprocess.run(command, capture_output=True, env=env)
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


def by_type(iterable, cls):
    """
    Find all the elements of an iterable which are of a given type.

    """
    return filter(lambda i: isinstance(i, cls), iterable)


def check_for_errors(results, caller_label=None):
    """
    A helper function for multiprocessing steps, checks a list of results for any exceptions and handles gracefully.
    """
    caller_label = f'during {caller_label}' if caller_label else ''

    exceptions = list(by_type(results, Exception))
    if exceptions:
        formatted_errors = "\n\n".join(map(str, exceptions))
        raise RuntimeError(
            f"{formatted_errors}\n\n{len(exceptions)} error(s) found {caller_label}"
        )
