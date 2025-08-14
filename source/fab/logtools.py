#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Logging tools for the fab framework.
"""

import sys
import logging
import inspect
from pathlib import Path
from typing import Optional


def make_logger(feature: str, offset: int = 1):
    """Create a hierarchical logger.

    The name of the logger is based on the module name of the caller
    and the calling function, but with the addition of the feature
    name at the second level of the hierarchy.

    If the logger is created in a module, no function name is
    appended.  If the logger is created from the __init__ method of a
    class, the name of the class is used in place of a function.

    :param feature: the name of the logging feature.  Typically
        either build or system.
    :param offset: the number of frames to skip.  Defaults to 1.
    :return: a logging.Logger instance.
    """

    # Get information about the caller using the inspect module
    finfo = inspect.stack()[offset]
    frame = finfo.frame
    code = frame.f_code
    module = inspect.getmodule(frame)
    if module is not None:
        parts = module.__name__.split(".")
    else:
        parts = ["root"]

    if (
        finfo.function == "__init__"
        and len(code.co_varnames)
        and code.co_varnames[0] == "self"
    ):
        # Use the class name
        parts.append(frame.f_locals["self"].__class__.__name__)
    elif finfo.function != "<module>":
        # Use the function name if not called directly in a module
        parts.append(finfo.function)

    # Clean up the name and insert the feature name
    parts = [i.replace("__", "") for i in parts]
    parts.insert(1, feature)

    # Finally assemble the logger
    return logging.getLogger(".".join(parts))


def make_loggers():
    """Create a set of named loggers.

    A simple convenience function that creates a pair of named loggers
    with build and system at the second level of the logging
    hierarchy.  This function is ignored when inspecting the calling
    tree to determine the name to use.

    :returns: tuple containing two logger instances, the first
        associated with the build hierarchy and the second with the system
        hierarchy.
    """

    return make_logger("build", 2), make_logger("system", 2)


class FabLogFilter(logging.Filter):
    """Class to filter log messages from the console stream.

    This filters out specific types of log message based on level
    criteria and the boolean quiet flag.  This makes it possible to
    write all log events to a file whilst controlling the amount of
    output seen by the user.
    """

    def __init__(
        self, build_level: Optional[int], system_level: Optional[int], quiet=False
    ):
        super().__init__()
        self.build_level = build_level
        self.system_level = system_level
        self.quiet = quiet

    def filter(self, record):
        """Decide whether to filter a specific log message."""

        if ".build" in record.name:
            # A build hierarchy message
            level = self.build_level
        else:
            # Assume all other messages are in the system category
            level = self.system_level

        if self.quiet and record.levelno < logging.ERROR:
            # Filter out everything except errors in quiet mode
            return False

        if (level is None or level <= 0) and record.levelno < logging.WARNING:
            # Filter out anything below warning
            return False

        if level == 1 and record.levelno < logging.INFO:
            # Filter out anything below info
            return False

        # Log all messages that have made it this far
        return True


def setup_logging(
    build_level: Optional[int],
    system_level: Optional[int],
    quiet=False,
    iostream=sys.stderr,
):
    """Setup the fab logging framework.

    Set output levels for build log messages and system log messages.

    Build messages are purely intended to be used to output
    information about the compile tasks.  System messages should help
    to debug the fab library itself.

    :param build_level: verbosity of output from the build logger
        hierarchy.  Setting to 0 or None implies a low level of
        output.
    :param system_level: verbosity of output from the system logger
        hierarchy.  Setting to 0 or None implies a low level of
        output.
    :param quiet: do not log anything lower than an error to the user
        output stream.
    :param iostream: output stream used to log messages.  Defaults to
        sys.stderr if not specified.  This is particularly useful when
        testing.
    """

    # Get the hierarchical logger
    fab_logger = logging.getLogger("fab")
    fab_logger.setLevel(logging.DEBUG)

    # Output format includes the module if running in debug mode
    if system_level is None or system_level == 0:
        formatter = logging.Formatter("%(asctime)s %(message)s")
    else:
        formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")

    # Create a python stream handler and set the formatting
    stream = logging.StreamHandler(iostream)
    stream.addFilter(FabLogFilter(build_level, system_level, quiet))
    stream.setFormatter(formatter)

    # Set fab messages to use the stream handler
    fab_logger.addHandler(stream)


def setup_file_logging(logfile: Path, name="root", create=True):
    """Direct log messages to a named file.

    :param logfile: path to the output log
    :param name: name of the logger hierarchy being added
    :param create: create the parent directory.  Defaults to True.
    """

    logfile = Path(logfile)

    if create:
        # Create the log directory
        logfile.parent.mkdir(parents=True, exist_ok=True)

    logfm = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logfh = logging.FileHandler(logfile)
    logfh.setLevel(logging.DEBUG)
    logfh.setFormatter(logfm)
    logging.getLogger(name).addHandler(logfh)
