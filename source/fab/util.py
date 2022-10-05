##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Various utility functions live here - until we give them a proper place to live!

"""

import datetime
import logging
import subprocess
import sys
import zlib
from collections import namedtuple
from pathlib import Path
from time import perf_counter
from typing import Iterator, Iterable, Optional, Set, Dict, List

from fab.dep_tree import AnalysedFile

logger = logging.getLogger(__name__)


def log_or_dot(logger, msg):
    """
    Util function which prints a fullstop without a newline, except in debug logging where it logs a message.

    """
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(msg)
    elif logger.isEnabledFor(logging.INFO):
        print('.', end='')
        sys.stdout.flush()


def log_or_dot_finish(logger):
    """
    Util function which completes the row of fullstops from :func:`~fab.util.log_or_dot`,
    by printing a newline when not in debug logging.

    """
    if logger.isEnabledFor(logging.INFO):
        print('')


HashedFile = namedtuple("HashedFile", ['fpath', 'file_hash'])


def file_checksum(fpath):
    """
    Return a checksum of the given file.

    This function is deterministic, returning the same result across Python invocations.

    We use crc32 for now because it's deterministic, unlike out-the-box hash.
    We could seed hash with a non-random or look into hashlib, if/when we want to improve this.

    """
    with open(fpath, "rb") as infile:
        return HashedFile(fpath, zlib.crc32(infile.read()))


def remove_minus_J(flags, verbose=False):
    """
    Remove the -J <folder> from the given flags.

    """
    # todo: Fab should be compiler aware, with the possibly of different flags to ignore per compiler
    in_minus_J = False
    ret = []
    for flag in flags:
        if in_minus_J:
            in_minus_J = False
            continue
        if flag == '-J':
            in_minus_J = True
        else:
            ret.append(flag)
    return ret


def flags_checksum(flags: List[str]):
    """
    Return a checksum of the flags, ignoring anything which should not cause a rebuild.

    """
    return string_checksum(str(remove_minus_J(flags)))


def string_checksum(s: str):
    """
    Return a checksum of the given string.

    This function is deterministic, returning the same result across Python invocations.

    We use crc32 for now because it's deterministic, unlike out-the-box hash.
    We could seed hash with a non-random or look into hashlib, if/when we want to improve this.

    """
    return zlib.crc32(s.encode())


def file_walk(path: Path) -> Iterator[Path]:
    """
    Return every file in *path* and its sub-folders.

    :param path:
        Folder to iterate.

    """
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
        self.start: Optional[float] = None
        self.taken: Optional[float] = None

    def __enter__(self):
        self.start = perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.taken = perf_counter() - self.start


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


# todo: move this
class CompiledFile(object):
    """
    A Fortran or C file which has been compiled.

    """
    def __init__(self, input_fpath, output_fpath):
        """
        :param input_fpath:
            The file that was compiled.
        :param output_fpath:
            The object file that was created.

        """
        # todo: Should just be the input_fpath, not the whole analysed file
        self.input_fpath = Path(input_fpath)
        self.output_fpath = Path(output_fpath)

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __repr__(self):
        return f'CompiledFile({self.input_fpath}, {self.output_fpath})'


# todo: we should probably pass in the output folder, not the project workspace
def input_to_output_fpath(config, input_path: Path):
    """
    Convert a path in the project's source folder to the equivalent path in the output folder.

    Allows the given path to already be in the output folder.

    :param config:
        The config object, which defines the source and output folders.
    :param input_path:
        The path to transform from input to output folders.

    """
    build_output = config.build_output

    # perhaps it's already in the output folder? todo: can use Path.is_relative_to from Python 3.9
    try:
        input_path.relative_to(build_output)
        return input_path
    except ValueError:
        pass
    rel_path = input_path.relative_to(config.source_root)
    return build_output / rel_path


def run_command(command, env=None, cwd=None):
    """
    Run a CLI command.

    :param command:
        List of strings to be sent to :func:`subprocess.run` as the command.
    :param env:
        Optional env for the command. By default it will use the current session's environment.

    """
    logger.debug(f'run_command: {command}')
    res = subprocess.run(command, capture_output=True, env=env, cwd=cwd)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed:\n{command}\n{res.stdout.decode()}\n{res.stderr.decode()}")

    return res.stdout.decode()


def suffix_filter(fpaths: Iterable[Path], suffixes: Iterable[str]):
    """
    Pull out all the paths with a given suffix from an iterable.

    :param fpaths:
        Iterable of paths.
    :param suffixes:
        Iterable of suffixes we want.

    """
    # todo: Just return the iterator from filter. Let the caller decide whether to turn into a list.
    return list(filter(lambda fpath: fpath.suffix in suffixes, fpaths))


def by_type(iterable, cls):
    """
    Find all the elements of an iterable which are of a given type.

    :param iterable:
        The iterable to search.
    :param cls:
        The type of the elements we want.

    """
    return filter(lambda i: isinstance(i, cls), iterable)


def get_mod_hashes(analysed_files: Set[AnalysedFile], config) -> Dict[str, int]:
    """
    Get the hash of every module file defined in the list of analysed files.

    """
    mod_hashes = {}
    for af in analysed_files:
        for mod_def in af.module_defs:
            fpath: Path = config.build_output / f'{mod_def}.mod'
            mod_hashes[mod_def] = file_checksum(fpath).file_hash

    return mod_hashes
