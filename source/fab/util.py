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
import os
import sys
import zlib
from argparse import ArgumentParser
from collections import namedtuple, defaultdict
from pathlib import Path
from time import perf_counter
from typing import Iterator, Iterable, Optional, Dict, Set, Union, List

import fab

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


def string_checksum(s: str):
    """
    Return a checksum of the given string.

    This function is deterministic, returning the same result across Python invocations.

    We use crc32 for now because it's deterministic, unlike out-the-box hash.
    We could seed hash with a non-random or look into hashlib, if/when we want to improve this.

    """
    return zlib.crc32(s.encode())


def file_walk(path: Union[str, Path], ignore_folders: Optional[List[Path]] = None) -> Iterator[Path]:
    """
    Return every file in *path* and its sub-folders.

    :param path:
        Folder to iterate.
    :param ignore_folders:
        Pass in any folder if you don't want to traverse into. Please see explanation and intended use, below.

    .. note::

        The prebuild folder can contain multiple versions of a single, generated fortran file,
        created by multiple runs of the build config. The prebuild folder stores these copies for when they're next
        needed, when they are copied out and reused. We usually won't want to include this folder when
        searching for source code to analyse.
        To meet these needs, this function will not traverse into the given folders, if provided.

    """
    path = Path(path)
    assert path.is_dir(), f"not dir: '{path}'"
    ignore_folders = ignore_folders or []

    # Note: path here *can* be the prebuild folder
    for i in path.iterdir():
        if i.is_dir():
            # Don't recurse into the given folders.
            if i in ignore_folders:
                logger.debug(f'file_walk ignoring {i}')
                continue
            yield from file_walk(path=i, ignore_folders=ignore_folders)
        else:
            yield i


class Timer():
    """
    A simple timing context manager.

    """
    def __init__(self) -> None:
        self.start: Optional[float] = None
        self.taken: Optional[float] = None

    def __enter__(self):
        self.start = perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert self.start is not None
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

    Note: This function can also handle paths which are not in the project workspace at all.
    This can happen when pointing the FindFiles step elsewhere, for example.
    In that case, the entire path will be made relative to the source folder instead of its anchor.

    """
    build_output = config.build_output

    # perhaps it's already in the output folder?
    try:
        input_path.relative_to(build_output)
        return input_path
    except ValueError:
        pass

    # try to convert it from the project source folder to the output folder
    try:
        rel_path = input_path.relative_to(config.source_root)
        return build_output / rel_path
    except ValueError:
        pass

    # It's neither in the project source folder nor the output folder.
    # This can happen if we're pointing the FindFiles step elsewhere.
    # We'll just have to convert the entire path to be inside the output folder.
    return build_output / '/'.join(input_path.parts[1:])


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


def get_fab_workspace() -> Path:
    """
    Read the Fab workspace from the `FAB_WORKSPACE` environment variable,
    defaulting to *~/fab-workspace*.

    """
    if os.getenv("FAB_WORKSPACE"):
        fab_workspace = Path(os.getenv("FAB_WORKSPACE"))  # type: ignore
    else:
        fab_workspace = Path(os.path.expanduser("~/fab-workspace"))
        logger.info(f"FAB_WORKSPACE not set, defaulting to {fab_workspace}")
    return fab_workspace


def get_prebuild_file_groups(prebuild_files: Iterable[Path]) -> Dict[str, Set]:
    """
    Group prebuild filenames by originating artefact.

    Prebuild filenames have the form `<stem>.<hash>.<suffix>`.
    This function creates a dict with wildcard key `<stem>.*.<suffix>`
    with each entry mapping to a set of all matching prebuild files.

    Given the input files *my_mod.123.o* and *my_mod.456.o*,
    returns a dict {'my_mod.*.o': {'my_mod.123.o', 'my_mod.456.o'}}

    """
    pbf_groups = defaultdict(set)

    for pbf in prebuild_files:
        stem_stem = pbf.stem.split('.')[0]
        wildcard_key = f'{stem_stem}.*{pbf.suffix}'
        pbf_groups[wildcard_key].add(pbf)

    return pbf_groups


def common_arg_parser() -> ArgumentParser:
    """
    A helper function returning an argument parser with common, useful arguments controlling command line tools.

    More arguments can be added. The caller must call `parse_args` on the returned parser.

    """
    # consider adding preprocessor, linker, optimisation, two-stage
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--verbose', action='store_true', help='DEBUG level logging')
    arg_parser.add_argument('--version', action='version', version=f'%(prog)s {fab.__version__}')
    group = arg_parser.add_argument_group(
        title='common arguments',
        description='Common arguments which can be passed to the BuildConfig.')
    arg_parser.add_argument('folder', nargs='?', default='.', type=Path, help='Source path')
    group.add_argument('--project_label', default=None, help='Project Label')
    group.add_argument('--fab_workspace', nargs='?', default=None, help='Fab working directory')
    group.add_argument('--multiprocessing', default=True, help='Turns OFF multiprocessing.')
    group.add_argument('--two-stage', action='store_true',
                       help='Compile .mod files first in a separate pass. Theoretically faster in some projects.')
    return arg_parser
