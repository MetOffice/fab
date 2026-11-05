from logging import DEBUG, ERROR, INFO, Logger, LogRecord, getLogger
from multiprocessing import Process

from fabengine.logserver import EventLogFilter, LoggingServer, make_logger, make_loggers
from pytest import mark, raises


class TestMakeLogger:
    """Check creation of loggers works as expected."""

    def test_function_logger(self):
        """Create a single logger in the user hierarchy."""

        logger = make_logger("user")
        assert isinstance(logger, Logger)
        assert ".user." in logger.name
        assert logger.name.endswith(".test_function_logger")

    def test_class_logger(self):
        """Create a logger inside an instance."""

        class MyClass:
            """Example class."""

            def __init__(self):
                self.logger = make_logger("user")

        m = MyClass()
        assert isinstance(m.logger, Logger)
        assert ".user." in m.logger.name
        assert m.logger.name.endswith(".MyClass")

    def test_multiple_loggers(self):
        """Create build and system loggers."""

        loggers = make_loggers()
        assert len(loggers) == 2
        assert all(isinstance(i, Logger) for i in loggers)
        assert ".user." in loggers[0].name
        assert ".system." in loggers[1].name
        assert loggers[0].name.endswith(".test_multiple_loggers")
        assert loggers[1].name.endswith(".test_multiple_loggers")


@mark.parametrize(
    "user, system, other, level, name, result",
    [
        (DEBUG, None, None, DEBUG, "toy.user", True),
        (INFO, None, None, DEBUG, "toy.user", False),
        (DEBUG, None, None, DEBUG, "toy.user.module", True),
        (None, DEBUG, None, DEBUG, "toy.system", True),
        (None, INFO, None, DEBUG, "toy.system", False),
        (None, DEBUG, None, DEBUG, "toy.system.module", True),
        (None, None, DEBUG, DEBUG, "toy", True),
        (None, None, INFO, DEBUG, "toy", False),
        (None, None, INFO, DEBUG, "toy.module", False),
        (DEBUG, None, None, ERROR, "toy.system", True),
    ],
    ids=[
        "user allow",
        "user block",
        "user+module allow",
        "system allow",
        "system block",
        "system+module allow",
        "other allow",
        "other block",
        "other+module allow",
        "user system error allow",
    ],
)
def test_event_filter(user, system, other, level, name, result):

    event = EventLogFilter(user, system, other)
    record = LogRecord(name, level, "test_logserver.py", 1, "test", (), None)

    assert event.filter(record) is result


def worker():
    """Trivial worker function."""
    getLogger("toy.user").info("test from worker")


def test_server(capsys):
    server = LoggingServer(user_level=INFO)

    with server:
        getLogger("toy.user").info("test from parent")

        wp = Process(target=worker)
        wp.start()
        wp.join()

    _, err = capsys.readouterr()
    assert "test from parent" in err
    assert "test from worker" in err


def test_server_logfile(tmp_path):
    log = tmp_path / "test.log"

    with LoggingServer(user_level=INFO, logfile=log):
        getLogger("toy.user").info("user information")
        getLogger("toy.user").debug("user debug")
        getLogger("toy.system").info("system information")
        getLogger("toy.system").debug("system debug")
        getLogger("toy.other").info("other information")
        getLogger("toy.other").debug("other debug")

    assert log.exists()

    lines = "".join(log.open("rt").readlines())

    assert "INFO:MainProcess:toy.user:user information\n" in lines
    assert "DEBUG:MainProcess:toy.user:user debug\n" in lines
    assert "INFO:MainProcess:toy.system:system information\n" in lines
    assert "DEBUG:MainProcess:toy.system:system debug\n" in lines
    assert "INFO:MainProcess:toy.other:other information\n" in lines
    assert "DEBUG:MainProcess:toy.other:other debug\n" in lines


def test_server_exceptions(capsys, tmp_path):

    log = tmp_path / "test.log"

    with raises(RuntimeError) as exc_info, LoggingServer(user_level=INFO, logfile=log):
        raise RuntimeError("test error logging")

    assert exc_info.type is RuntimeError

    _, err = capsys.readouterr()
    assert "An exception has occurred" in err
    assert "RuntimeError: test error logging" in err

    assert log.exists()

    lines = "".join(log.open("rt").readlines())

    assert (
        "ERROR:MainProcess:fabengine.system.logserver.exit:An exception has occurred\n"
        in lines
    )
    assert "RuntimeError: test error logging" in lines
