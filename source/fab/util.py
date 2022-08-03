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
from typing import Iterator, Iterable, Optional, Set, Dict

from fab.dep_tree import AnalysedFile

from fab.constants import BUILD_OUTPUT

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


HashedFile = namedtuple("HashedFile", ['input_fpath', 'file_hash'])


def file_checksum(fpath):
    """
    Return a checksum of the given file.

    This function is deterministic, returning the same result across Python invocations.

    We use crc32 for now because it's deterministic, unlike out-the-box hash.
    We could seed hash with a non-random or look into hashlib, if/when we want to improve this.

    """
    with open(fpath, "rb") as infile:
        return HashedFile(fpath, zlib.crc32(infile.read()))


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
    def __init__(self, input_fpath, output_fpath,
                 source_hash=None, flags_hash=None, module_deps_hashes: Dict[str, int] = None):
        """
        :param input_fpath:
            The file that was compiled.
        :param output_fpath:
            The object file that was created.

        """
        # todo: Should just be the input_fpath, not the whole analysed file
        self.input_fpath = Path(input_fpath)
        self.output_fpath = Path(output_fpath)

        self.source_hash = source_hash or 0
        self.flags_hash = flags_hash or 0
        self.module_deps_hashes = module_deps_hashes or {}

    #
    # persistence
    #
    @classmethod
    def field_names(cls):
        return [
            'input_fpath', 'output_fpath',
            'source_hash', 'flags_hash', 'module_deps_hashes',
        ]

    def to_str_dict(self):
        """
        Convert to a dict of strings. For example, when writing to a CsvWriter.

        """
        return {
            "input_fpath": str(self.input_fpath),
            "output_fpath": str(self.output_fpath),
            "source_hash": str(self.source_hash),
            "flags_hash": str(self.flags_hash),
            "module_deps_hashes": ';'.join([f'{k}={v}' for k, v in self.module_deps_hashes.items()]),
        }

    @classmethod
    def from_str_dict(cls, d):
        """Convert from a dict of strings. For example, when reading from a CsvWriter."""

        if d["module_deps_hashes"]:
            # json would be easier now we're also serialising dicts
            module_deps_hashes = [i.split('=') for i in d["module_deps_hashes"].split(';')]
            module_deps_hashes = {i[0]: int(i[1]) for i in module_deps_hashes}
        else:
            module_deps_hashes = {}

        return cls(
            input_fpath=Path(d["input_fpath"]),
            output_fpath=Path(d["output_fpath"]),
            source_hash=int(d["source_hash"]),
            flags_hash=int(d["flags_hash"]),
            module_deps_hashes=module_deps_hashes,
        )

    def __eq__(self, other):
        return vars(self) == vars(other)


# todo: we should probably pass in the output folder, not the project workspace
def input_to_output_fpath(source_root: Path, project_workspace: Path, input_path: Path):
    """
    Convert a path in the project's source folder to the equivalent path in the output folder.

    Allows the given path to already be in the output folder.

    :param source_root:
        The project's source folder. This can sometimes be outside the project workspace.
    :param project_workspace:
        The project's workspace folder, in which the output folder can be found.

    """
    build_output = project_workspace / BUILD_OUTPUT

    # perhaps it's already in the output folder? todo: can use Path.is_relative_to from Python 3.9
    try:
        input_path.relative_to(build_output)
        return input_path
    except ValueError:
        pass
    rel_path = input_path.relative_to(source_root)
    return build_output / rel_path


def run_command(command, env=None):
    """
    Run a CLI command.

    :param command:
        List of strings to be sent to :func:`subprocess.run` as the command.
    :param env:
        Optional env for the command. By default it will use the current session's environment.

    """
    logger.debug(f'run_command: {command}')
    res = subprocess.run(command, capture_output=True, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed:\n{command}\n{res.stderr.decode()}")


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
            fpath: Path = config.project_workspace / BUILD_OUTPUT / f'{mod_def}.mod'
            mod_hashes[mod_def] = file_checksum(fpath).file_hash

    return mod_hashes
