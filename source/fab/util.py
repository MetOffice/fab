import logging


def log_or_dot(logger, msg):
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(msg)
    elif logger.isEnabledFor(logging.INFO):
        print('.', end='')


def log_or_dot_finish(logger):
    if logger.isEnabledFor(logging.INFO):
        print('')
