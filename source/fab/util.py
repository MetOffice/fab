import logging
from collections import namedtuple
from pathlib import Path


def log_or_dot(logger, msg):
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(msg)
    elif logger.isEnabledFor(logging.INFO):
        print('.', end='')


def log_or_dot_finish(logger):
    if logger.isEnabledFor(logging.INFO):
        print('')


FileHash = namedtuple("FileHash", ['fpath', 'hash'])


def do_hash(fpath: Path):
    with open(fpath) as infile:
        return FileHash(fpath, hash(infile.read()))
