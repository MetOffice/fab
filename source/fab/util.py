import logging
import re
import subprocess
import sys
import zlib
from collections import namedtuple
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Iterator

from fab.constants import BUILD_SOURCE, BUILD_OUTPUT

logger = logging.getLogger('fab')
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


def fixup_command_includes(command, source_root, file_path):
    """

    E.g:

        fixup_command_includes(
            command=['-I', '/abs_inc', '-I', 'rel_inc'],
            source_root=Path('/home/usr/me/git/proj/build_source'),
            file_path=Path('/home/usr/me/git/proj/build_source/sub/file.f90')
        )

        >>> ['-I', '/home/usr/me/git/proj/build_source/abs_inc', '-I', '/home/usr/me/git/proj/build_source/sub/rel_inc']

    """

    for i in range(len(command)):
        part = command[i]

        if part == "-I":
            inc_path = Path(command[i+1])

            if inc_path.is_absolute():
                rel_path = inc_path.parts[1:]  # take off the leading slash
                new_inc_path = source_root.joinpath(*rel_path)
                command[i+1] = str(new_inc_path)
            else:
                # E.g an include subfolder below a c file
                command[i+1] = str(file_path.parent / inc_path)


def input_to_output_fpath(workspace: Path, input_path: Path):
    rel_path = input_path.relative_to(workspace / BUILD_SOURCE)
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
