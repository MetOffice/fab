##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Unit tests for custom fab exceptions.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, PropertyMock

from fab.errors import (
    FabError,
    FabToolError,
    FabToolMismatch,
    FabToolInvalidVersion,
    FabToolPsycloneAPI,
    FabToolNotAvailable,
    FabToolInvalidSetting,
    FabAnalysisError,
    FabCommandError,
    FabCommandNotFound,
    FabFileLoadError,
    FabHashError,
    FabMultiCommandError,
    FabSourceNoFilesError,
    FabSourceMergeError,
    FabSourceFetchError,
    FabUnknownLibraryError,
)


class TestErrors:
    """Basic tests for the FabError class hierarchy."""

    def test_base(self):
        """Test the base Fab error class."""

        err = FabError("test message")
        assert str(err) == "test message"

    def test_unknown_library(self):
        """Test unknown library errors."""

        err = FabUnknownLibraryError("mylib")
        assert str(err) == "unknown library 'mylib'"

    @pytest.mark.parametrize(
        "fpath,lineno,message",
        [
            (None, None, "test message"),
            (Path("/tmp/myfile.f90"), None, "test message (myfile.f90)"),
            (Path("/tmp/myfile.f90"), 2, "test message (myfile.f90:2)"),
        ],
        ids=["message only", "fpath", "fpath+lineno"],
    )
    def test_fab_analysis_error(self, fpath, lineno, message):
        """Test analsys/parse errors."""

        err = FabAnalysisError("test message", fpath, lineno)
        assert str(err) == message

    def test_fab_file_load_error(self):

        err = FabFileLoadError("test message", Path("/tmp/FabFile"))
        assert str(err) == "test message"


class TestToolErrors:
    """Test the FabToolError hierarchy."""

    def test_tool_string(self):
        """Test the base FabToolError class."""

        err = FabToolError("cc", "compiler message")
        assert str(err) == "[cc] compiler message"

        # Mock defines an internal name property, so special handling
        # is required to reset the value to support testing
        category = Mock()
        del category._name
        type(category).name = PropertyMock(return_value="category cc")
        err = FabToolError(category, "compiler message")
        assert str(err) == "[category cc] compiler message"

    def test_mismatch(self):
        """Test tool type mismatch class."""

        err = FabToolMismatch("cc", "CCompiler", "Ar")
        assert str(err) == "[cc] got type CCompiler instead of Ar"

    def test_invalid_version(self):
        """Test invalid version class."""

        err = FabToolInvalidVersion("cc", "abc")
        assert str(err) == "[cc] invalid version 'abc'"

        err = FabToolInvalidVersion("cc", "abc", "VV.NN")
        assert str(err) == "[cc] invalid version 'abc' should be 'VV.NN'"

    def test_psyclone_api(self):
        """Test PSyclone API  class."""

        err = FabToolPsycloneAPI(None, "alg_file")
        assert str(err) == "[psyclone] called without API but not with alg_file"

        err = FabToolPsycloneAPI("nemo", "alg_file")
        assert str(err) == "[psyclone] called with nemo API but not with alg_file"

        err = FabToolPsycloneAPI("nemo", "alg_file", present=True)
        assert str(err) == "[psyclone] called with nemo API and with alg_file"

    def test_not_available(self):
        """Test tool not available class."""

        err = FabToolNotAvailable("psyclone")
        assert str(err) == "[psyclone] not available"

        err = FabToolNotAvailable("gfortran", "GCC")
        assert str(err) == "[gfortran] not available in GCC"

    def test_invalid_setting(self):
        """Test invalid setting class."""

        err = FabToolInvalidSetting("category", "compiler")
        assert str(err) == "[compiler] invalid category"

        err = FabToolInvalidSetting("category", "compiler", "nosuch")
        assert str(err) == "[compiler] invalid category nosuch"


class TestCommandErrors:
    """Test various command errors."""

    def test_command(self):
        """Test FabCommandError in various configurations."""

        err = FabCommandError(["ls", "-l", "/nosuch"], 1, b"", b"ls: cannot", "/")
        assert str(err) == "return code 1 from 'ls -l /nosuch'"

    def test_not_found(self):
        """Test command not found errors."""

        err = FabCommandNotFound(["ls", "-l"])
        assert str(err) == "unable to execute 'ls'"

        err = FabCommandNotFound("ls -l")
        assert str(err) == "unable to execute 'ls'"

        with pytest.raises(ValueError) as exc:
            FabCommandNotFound({"a": 1})
        assert "invalid command" in str(exc.value)

    def test_multi(self):
        """Test multiprocessing command errors."""

        err = FabMultiCommandError([ValueError("invalid value")])
        assert str(err) == "1 exception during multiprocessing"

        err = FabMultiCommandError(
            [ValueError("invalid value"), TypeError("invalid type")]
        )
        assert str(err) == "2 exceptions during multiprocessing"

        err = FabMultiCommandError(
            [ValueError("invalid value"), TypeError("invalid type")], "during psyclone"
        )
        assert str(err) == "2 exceptions during psyclone"


class TestSourceErrors:
    """Test the source errors hierarchy."""

    def test_no_files(self):
        """Test lack of source files."""

        err = FabSourceNoFilesError()
        assert str(err) == "no source files found after filtering"

    def test_merge(self):
        """Test merge errors."""

        tool = Mock()
        type(tool).name = PropertyMock(return_value="git")

        err = FabSourceMergeError(tool, "conflicting source files")
        assert str(err) == "[git] merge failed: conflicting source files"

        err = FabSourceMergeError(tool, "conflicting source files", "vn1.1")
        assert str(err) == "[git] merge of 'vn1.1' failed: conflicting source files"

    def test_fetch(self):
        """Test fetch errors."""

        err = FabSourceFetchError("/my/dir1", "no such directory")
        assert str(err) == "could not fetch /my/dir1: no such directory"


class TestAnalyse:
    """Test analyse and source processing exceptions."""

    def test_hash(self):

        err = FabHashError(Path("/abc/test.f90"))
        assert str(err) == "failed to create hash for /abc/test.f90"
