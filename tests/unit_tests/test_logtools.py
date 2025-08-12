#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Unit tests for fab.logtools.
"""


import logging
import re
from io import StringIO
from fab.logtools import make_logger, make_loggers, setup_logging, setup_file_logging

import pytest


class TestCreateLoggers:
    """Check creation of loggers works as expected."""

    def test_function_logger(self):
        """Create a single logger in the build hierarchy."""

        logger = make_logger("build")
        assert isinstance(logger, logging.Logger)
        assert ".build." in logger.name
        assert logger.name.endswith(".test_function_logger")

    def test_class_logger(self):
        """Create a logger inside an instance."""

        class MyClass:
            """Example class."""

            def __init__(self):
                self.logger = make_logger("build")

        m = MyClass()
        assert isinstance(m.logger, logging.Logger)
        assert ".build." in m.logger.name
        assert m.logger.name.endswith(".MyClass")

    def test_multiple_loggers(self):
        """Create build and system loggers."""

        loggers = make_loggers()
        assert len(loggers) == 2
        assert all(isinstance(i, logging.Logger) for i in loggers)
        assert ".build." in loggers[0].name
        assert ".system." in loggers[1].name
        assert loggers[0].name.endswith(".test_multiple_loggers")
        assert loggers[1].name.endswith(".test_multiple_loggers")


class TestSetupLogging:
    """Test the setup_logging() function with range of settings."""

    @pytest.mark.parametrize(
        "blevel,slevel,expected",
        [
            (
                0,
                0,
                set(["build error", "build warning", "system error", "system warning"]),
            ),
            (
                1,
                0,
                set(
                    [
                        "build error",
                        "build warning",
                        "system error",
                        "system warning",
                        "build info",
                    ]
                ),
            ),
            (
                2,
                0,
                set(
                    [
                        "build error",
                        "build warning",
                        "system error",
                        "system warning",
                        "build info",
                        "build debug",
                    ]
                ),
            ),
            (
                0,
                1,
                set(
                    [
                        "build error",
                        "build warning",
                        "system error",
                        "system warning",
                        "system info",
                    ]
                ),
            ),
            (
                0,
                2,
                set(
                    [
                        "build error",
                        "build warning",
                        "system error",
                        "system warning",
                        "system info",
                        "system debug",
                    ]
                ),
            ),
        ],
        ids=["nothing", "build info", "build debug", "system info", "system debug"],
    )
    def test_levels(self, blevel, slevel, expected, caplog):
        """Test the various different log level combinations."""

        messages = StringIO()

        build_logger = logging.getLogger("fab.build")
        system_logger = logging.getLogger("fab.system")

        setup_logging(blevel, slevel, False, messages)
        build_logger.error("build error")
        build_logger.warning("build warning")
        build_logger.info("build info")
        build_logger.debug("build debug")

        system_logger.error("system error")
        system_logger.warning("system warning")
        system_logger.info("system info")
        system_logger.debug("system debug")

        found = set([])

        for line in messages.getvalue().split("\n"):
            # The regexp contains an optional middle section to match both
            # build and system message formats
            match = re.match(r"^\S+\s+\S+\s+(?:fab\.\S+\s+[A-Z]+\s+)?(.*)$", line)
            if match:
                found.add(match.group(1))

        assert found == expected

    @pytest.mark.parametrize(
        "blevel,slevel",
        [
            (0, 0),
            (1, 0),
            (2, 0),
            (0, 1),
            (0, 2),
        ],
        ids=["nothing", "build info", "build debug", "system info", "system debug"],
    )
    def test_quiet(self, blevel, slevel, caplog):
        """Check quiet mode suppresses everything except errors.

        This captures the output from the stream handler and confirm
        that it has been filtered correctly using a StringIO instance
        to intercept the output.
        """

        build_logger = logging.getLogger("fab.build")
        system_logger = logging.getLogger("fab.system")

        messages = StringIO()

        setup_logging(blevel, slevel, True, messages)
        build_logger.error("build error")
        build_logger.warning("build warning")
        build_logger.info("build info")
        build_logger.debug("build debug")

        system_logger.error("system error")
        system_logger.warning("system warning")
        system_logger.info("system info")
        system_logger.debug("system debug")

        text = messages.getvalue()

        assert "build error" in text
        assert "build warning" not in text
        assert "build info" not in text
        assert "build debug" not in text

        assert "system error" in text
        assert "system warning" not in text
        assert "system info" not in text
        assert "system debug" not in text

    @pytest.mark.parametrize(
        "slevel,pattern",
        [
            (0, r"^\S+\s+\S+\s+test\s+message$"),
            (1, r"^\S+\s+\S+\s+fab.build\s+INFO\s+test\s+message$"),
        ],
        ids=["build", "system"],
    )
    def test_formatting(self, slevel, pattern, caplog):
        """Check formatting changes when system logging is used."""

        messages = StringIO()
        setup_logging(1, slevel, False, messages)

        logging.getLogger("fab.build").info("test message")
        text = messages.getvalue()

        assert re.match(pattern, text) is not None


def test_file_logging(tmp_path, caplog):
    """Check that file logging works as expected."""

    logfile = tmp_path / "subdir" / "test.log"
    setup_file_logging(logfile)

    fab = logging.getLogger("fab.build")
    fab.setLevel(logging.DEBUG)

    fab.info("build info")
    fab.debug("build debug")

    assert logfile.is_file()

    with logfile.open("r") as fd:
        lines = "".join(fd.readlines())

    assert "build info" in lines
    assert "build debug" in lines
