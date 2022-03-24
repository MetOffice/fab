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
from abc import ABC, abstractmethod
from collections import namedtuple
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Iterator, List, Iterable, Dict

from fab.constants import BUILD_OUTPUT, SOURCE_ROOT

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stderr))


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
    try:
        res = subprocess.run(command, check=True)
        if res.returncode != 0:
            # todo: specific exception
            raise Exception(f"The command exited with non zero: {res.stderr.decode()}")
    except Exception as err:
        raise Exception(f"error: {err}")


def suffix_filter(fpaths: Iterable[Path], suffixes: Iterable[str]):
    return list(filter(lambda fpath: fpath.suffix in suffixes, fpaths))


############

# todo: docstrings for these

# todo: poor name?
class SourceGetter(ABC):
    @abstractmethod
    def __call__(self, artefacts):
        pass


# todo: problematic name? It's pulling out an artefact collection, not a single artefact...
class Artefact(SourceGetter):

    def __init__(self, name):
        self.name = name

    def __call__(self, artefacts):
        super().__call__(artefacts)
        return artefacts[self.name]


# todo: not ideal for name to just add an s
class Artefacts(SourceGetter):
    # todo: this assumes artefactsa are lists, which might not always be the case? discuss or change

    def __init__(self, names: List[str]):
        self.names = names

    def __call__(self, artefacts: Dict):
        super().__call__(artefacts)
        result = []
        for name in self.names:
            result.extend(artefacts.get(name, []))
        return result


# Artefact filtering config - should probably live in steps/__init__.py
class FilterFpaths(SourceGetter):

    def __init__(self, artefact_name: str, suffixes: List[str]):
        self.artefact_name = artefact_name
        self.suffixes = suffixes

    # def __call__(self, *args, **kwargs):
    def __call__(self, artefacts):
        super().__call__(artefacts)
        fpaths: Iterable[Path] = artefacts[self.artefact_name]
        return suffix_filter(fpaths, self.suffixes)


# todo: improve these filters? they are similar
class FilterBuildTree(SourceGetter):

    def __init__(self, suffixes: List[str], artefact_name: str = 'build_tree'):
        self.artefact_name = artefact_name
        self.suffixes = suffixes

    # def __call__(self, *args, **kwargs):
    def __call__(self, artefacts):
        super().__call__(artefacts)
        analysed_files: Iterable[Path] = artefacts[self.artefact_name].values()
        return list(filter(lambda af: af.fpath.suffix in self.suffixes, analysed_files))
