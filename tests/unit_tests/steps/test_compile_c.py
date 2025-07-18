# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Exercises the compiler step.
"""
from pathlib import Path
from unittest.mock import Mock

from pytest import fixture, raises, warns
from pytest_subprocess.fake_process import FakeProcess

from fab.artefacts import ArtefactSet
from fab.build_config import AddFlags, BuildConfig
from fab.parse.c import AnalysedC
from fab.steps.compile_c import _get_obj_combo_hash, _compile_file, compile_c
from fab.tools.category import Category
from fab.tools.flags import Flags
from fab.tools.tool_box import ToolBox


@fixture(scope='function')
def content(tmp_path: Path, stub_tool_box: ToolBox):
    """
    Provides a test environment consisting of a config instance, analysed
    file.
    """
    config = BuildConfig('proj',
                         stub_tool_box,
                         multiprocessing=False,
                         fab_workspace=tmp_path)

    analysed_file = AnalysedC(fpath=Path(f'{config.source_root}/foo.c'),
                              file_hash=0)
    config._artefact_store[ArtefactSet.BUILD_TREES] = \
        {None: {analysed_file.fpath: analysed_file}}
    return config, analysed_file


def test_compile_c_wrong_compiler(content, fake_process: FakeProcess) -> None:
    """
    Tests wrong kind of compiler.

    ToDo: Can this ever happen? And monkeying with "private" state again.
    """
    config = content[0]

    fake_process.register(['scc', '--version'], stdout='1.2.3')

    tb = config.tool_box
    # Take the Fortran compiler
    cc = tb[Category.C_COMPILER]
    # So overwrite the C compiler with the re-categorised Fortran compiler
    cc._is_available = True
    tb.add_tool(cc, silent_replace=True)
    cc._category = Category.FORTRAN_COMPILER

    # Now check that _compile_file detects the incorrect class of the
    # C compiler
    mp_common_args = Mock(config=config)
    with raises(RuntimeError) as err:
        _compile_file((Mock(), mp_common_args))
    assert str(err.value) == ("Unexpected tool 'some C compiler' of category "
                              "'FORTRAN_COMPILER' instead of CCompiler")


# This is more of an integration test than a unit test
class TestCompileC:
    '''Test various functionalities of the C compilation step.'''

    def test_vanilla(self, content,
                     fake_process: FakeProcess) -> None:
        """
        Tests correct use of compiler.
        """
        config, _ = content

        fake_process.register(['scc', '--version'], stdout='1.2.3')
        fake_process.register([
            'scc', '-c', '-I', 'foo/include',
            '-Dhello', 'foo.c',
            '-o', str(config.prebuild_folder / 'foo.18f203cab.o')
        ])
        with warns(UserWarning, match="_metric_send_conn not set, "
                                      "cannot send metrics"):
            compile_c(config=config,
                      path_flags=[AddFlags(match='$source/*',
                                           flags=['-I', 'foo/include',
                                                  '-Dhello'])])

        # ensure it created the correct artefact collection
        assert config.artefact_store[ArtefactSet.OBJECT_FILES] == {
            None: {config.prebuild_folder / 'foo.18f203cab.o', }
        }

    def test_exception_handling(self, content,
                                fake_process: FakeProcess) -> None:
        """
        Tests compiler failure.
        """
        config, _ = content

        fake_process.register(['scc', '--version'], stdout='1.2.3')
        fake_process.register([
            'scc', '-c', 'foo.c',
            '-o', str(config.build_output / '_prebuild/foo.101865856.o')
        ], returncode=1)
        with raises(RuntimeError):
            compile_c(config=config)


class TestGetObjComboHash:
    '''Tests the object combo hash functionality.'''

    @fixture(scope='function')
    def flags(self):
        '''Returns the flag for these tests.'''
        return Flags(['-Denv_flag', '-I', 'foo/include', '-Dhello'])

    def test_vanilla(self, content, flags, fake_process: FakeProcess) -> None:
        """
        Tests hashing.
        """
        config, analysed_file = content

        fake_process.register(['scc', '--version'], stdout='1.2.3')
        compiler = config.tool_box[Category.C_COMPILER]
        #
        # ToDo: Messing with "private" members.
        #
        result = _get_obj_combo_hash(config, compiler, analysed_file, flags)
        assert result == 5289295574

    def test_change_file(self, content, flags,
                         fake_process: FakeProcess) -> None:
        """
        Tests changes to source file changes the hash.
        """
        config, analysed_file = content

        fake_process.register(['scc', '--version'], stdout='1.2.3')
        compiler = config.tool_box[Category.C_COMPILER]
        #
        # ToDo: Messing with "private" members.
        #
        analysed_file._file_hash += 1
        result = _get_obj_combo_hash(config, compiler, analysed_file, flags)
        assert result == 5289295575

    def test_change_flags(self, content, flags,
                          fake_process: FakeProcess) -> None:
        """
        Tests changing compiler arguments changes the hash.
        """
        config, analysed_file = content

        fake_process.register(['scc', '--version'], stdout='1.2.3')
        compiler = config.tool_box[Category.C_COMPILER]
        flags = Flags(['-Dfoo'] + flags)
        result = _get_obj_combo_hash(config, compiler, analysed_file, flags)
        assert result != 5066163117

    def test_change_compiler(self, content, flags,
                             fake_process: FakeProcess) -> None:
        """
        Tests a change in compiler name changes the hash.
        """
        config, analysed_file = content

        fake_process.register(['scc', '--version'], stdout='1.2.3')
        compiler = config.tool_box[Category.C_COMPILER]
        #
        # Change the name of the compiler
        #
        # ToDo: Is this something which can ever happen and we shouldn't be
        #       messing with "private" members.
        #
        compiler._name = compiler.name + "XX"
        result = _get_obj_combo_hash(config, compiler, analysed_file, flags)
        assert result != 5066163117

    def test_change_compiler_version(self, content, flags) -> None:
        """
        Tests a change in the compiler version number changes the hash.
        """
        config, analysed_file = content
        compiler = config.tool_box[Category.C_COMPILER]
        compiler._version = (9, 8, 7)
        #
        # ToDo: Messing with "private" members.
        #
        result = _get_obj_combo_hash(config, compiler, analysed_file, flags)
        assert result != 5066163117
