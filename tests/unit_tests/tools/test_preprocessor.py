##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests source preprocessor tools.
"""
from logging import Logger
from pathlib import Path

from pytest import mark
from pytest_subprocess.fake_process import FakeProcess

from fab.build_config import BuildConfig
from fab.tools.category import Category
from fab.tools.preprocessor import Cpp, CppFortran, Fpp, Preprocessor

from tests.conftest import call_list, ExtendedRecorder


def test_constructor() -> None:
    """
    Tests construction from argument list.
    """
    tool = Preprocessor("some preproc", "spp", Category.FORTRAN_PREPROCESSOR)
    assert str(tool) == "Preprocessor - some preproc: spp"
    assert tool.exec_name == "spp"
    assert tool.name == "some preproc"
    assert tool.category == Category.FORTRAN_PREPROCESSOR
    assert isinstance(tool.logger, Logger)


@mark.parametrize('rc', [0, 1])
def test_fpp_is_available(rc, fake_process: FakeProcess) -> None:
    """
    Tests availability check for Intel's "fpp" tool.
    """
    command = ['fpp', '-what']
    fake_process.register(command, returncode=rc)

    fpp = Fpp()
    assert fpp.is_available is (rc == 0)
    assert call_list(fake_process) == [command]


class TestCpp:
    """
    Tests the C preprocessor.
    """
    def test_cpp(self, subproc_record: ExtendedRecorder) -> None:
        """
        Tests the CPP tool.
        """
        cpp = Cpp()
        cpp.run("--version")
        assert subproc_record.invocations() == [['cpp', '--version']]

    def test_is_not_available(self, fake_process: FakeProcess) -> None:
        """
        Tests if a preprocessor is not abailable
        """
        fake_process.register(['cpp', '--version'], returncode=1)
        cpp = Cpp()
        assert cpp.is_available is False
        assert call_list(fake_process) == [['cpp', '--version']]


class TestCppTraditional:
    """
    Tests to verify that the traditional flags is used for the standard
    preprocessor in Fortran mode.
    """
    def test_is_not_available(self, fake_process: FakeProcess) -> None:
        """
        Tests CPP in "traditional" mode when the tool is not available.
        """
        command = ['cpp', '--version']
        fake_process.register(command, returncode=1)

        cppf = CppFortran()
        assert cppf.is_available is False
        assert call_list(fake_process) == [command]

    def test_preprocess(self,
                        stub_configuration: BuildConfig,
                        subproc_record: ExtendedRecorder) -> None:
        """Tests the combination of various sources of flags:
        tool and additional flags.
        """
        cppf = CppFortran()
        cppf.add_flags(["-Dtool-specific-flag"])
        cppf.preprocess(Path("a.in"), Path("a.out"), stub_configuration)
        cppf.preprocess(Path("a.in"), Path("a.out"), stub_configuration,
                        ["-DDO_SOMETHING"])
        assert subproc_record.invocations() == [
            ["cpp", "-Dtool-specific-flag", "-traditional-cpp", "-P", "a.in",
             "a.out"],
            ["cpp", "-Dtool-specific-flag", "-traditional-cpp", "-P",
             "-DDO_SOMETHING", "a.in", "a.out"]
        ]
