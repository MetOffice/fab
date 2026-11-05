from inspect import getmodule, stack
from logging import (
    DEBUG,
    ERROR,
    FileHandler,
    Filter,
    Formatter,
    Logger,
    LogRecord,
    StreamHandler,
    getLogger,
)
from logging.handlers import QueueHandler, QueueListener
from multiprocessing import Queue
from pathlib import Path
from warnings import filterwarnings


def make_logger(feature: str, offset: int = 1) -> Logger:
    """Create a hierarchical logger.

    The name of the logger is based on the module name of the caller
    and the calling function, but with the addition of the feature
    name at the second level of the hierarchy.

    If the logger is created in a module, no function name is
    appended.  If the logger is created from the __init__ method of a
    class, the name of the class is used in place of a function.

    :param feature: the name of the logging feature.  Typically
        either "build" or "system".
    :param offset: the number of interpreter stack frames to skip when
        finding the caller name.  Defaults to 1.
    :return: an appropriately named logger.
    """

    # Get information about the caller using the inspect module
    finfo = stack()[offset]
    frame = finfo.frame
    code = frame.f_code
    module = getmodule(frame)
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
    return getLogger(".".join(parts))


def make_loggers() -> tuple[Logger, Logger]:
    """Create a set of named loggers.
    A simple convenience function that creates a pair of named loggers
    with build and system at the second level of the logging
    hierarchy.  This function is ignored when inspecting the calling
    tree to determine the name to use.

    :return: tuple containing two logger instances, the first
        associated with the build hierarchy and the second with the system
        hierarchy.
    """

    return make_logger("user", 2), make_logger("system", 2)


class EventLogFilter(Filter):
    """Filter log events by name and priority level.

    When provided with a set of logging levels for the various
    different categories, filter out events which fall below the
    specified levels.  If a particular logging level is left
    unspecified, it defaults to ERROR.

    :param user_level: ignore user messages below this level.
    :param system_level: ignore system messags below this level.
    :param other_level: ignore all other types of message below this
        level.

    """

    def __init__(
        self,
        user_level: int | None = None,
        system_level: int | None = None,
        other_level: int | None = None,
    ):
        self._user_level = user_level or ERROR
        self._system_level = system_level or ERROR
        self._other_level = other_level or ERROR

    def filter(self, record: LogRecord) -> bool:
        """Whether record should be logged.

        Apply the different logging levels against the target record
        based on whether its name includes user or system or neither.

        :param record: a LogRecord instance.
        :return: True if record should be logged and False if it
            should be discarded.
        """
        if ".user." in record.name or record.name.endswith(".user"):
            return record.levelno >= self._user_level
        if ".system." in record.name or record.name.endswith(".system"):
            return record.levelno >= self._system_level
        return record.levelno >= self._other_level


class LoggingServer:
    """Logging server process.

    Use a queue to manage log messages from multiple parallel
    processes to ensure they are written out sequentially.  Provide
    the ability to write all messages to a logfile and the abilty to
    select which messages get written to the console output.

    :param logfile: path to the log file.  If specified, the log will
        include all messages passed to the logging framework.
    :param user_level: do not send user messages below this level to
        the console.
    :param system_level: do not send user messages below this level to
        the console.
    """

    def __init__(
        self,
        logfile: Path | None = None,
        user_level: int | None = None,
        system_level: int | None = None,
    ):
        self._logfile = logfile
        self._user_level = user_level
        self._system_level = system_level

        # Logging infrastructure
        self._messages: Queue = Queue()
        self._handler = QueueHandler(self._messages)
        self._listener = None
        root = getLogger()
        root.addHandler(self._handler)
        root.setLevel(DEBUG)

    def __enter__(self):
        """Start the logging server."""

        # It should be safe ignore process/threading warnings about
        # potential deadlocks because the build system only uses
        # processes and not threads
        filterwarnings(
            "ignore",
            message=".*may lead to deadlocks in the child.*",
            category=DeprecationWarning,
        )

        handlers = []

        if self._logfile is not None:
            formatter = Formatter(
                "%(asctime)s:%(levelname)s:%(processName)s:%(name)s:%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            fh = FileHandler(filename=self._logfile)
            fh.setFormatter(formatter)
            handlers.append(fh)

        formatter = Formatter(
            "%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        sh = StreamHandler()
        sh.setFormatter(formatter)
        sh.addFilter(EventLogFilter(self._user_level, self._system_level))
        handlers.append(sh)

        self._listener = QueueListener(self._messages, *handlers)
        self._listener.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Shut down the logging server.

        Ensure that exceptions are logged while the framework is still
        running and re-raise them to expose them to the caller.
        Always log a message before stopping the server.
        """

        system = make_logger("system")
        if exc_type is not None:
            system.exception("An exception has occurred")
        system.info("Stopping logging server")
        self._listener.stop()

        if exc_type is not None:
            raise
