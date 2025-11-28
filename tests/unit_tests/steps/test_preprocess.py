# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

"""
Tests running the Fortran preprocessor step.
"""
from pathlib import Path

from pytest import raises, warns
from pytest_subprocess.fake_process import FakeProcess

from fab.build_config import BuildConfig
from fab.steps.preprocess import preprocess_fortran
from fab.tools.category import Category
from fab.artefacts import ArtefactStore
from fab.tools.tool_box import ToolBox
from fab.tools.tool_repository import ToolRepository


class Test_preprocess_fortran:

    def test_big_little(self, tmp_path: Path,
                        stub_tool_repository: ToolRepository,
                        fake_process: FakeProcess) -> None:
        """
        Tests big F90 files are preprocessed and little f90 files are copied.
        """
        version_command = ['cpp', '-traditional-cpp', '-P', '--version']
        fake_process.register(version_command, stdout='1.2.3')
        process_command = ['cpp', '-traditional-cpp', '-P',
                           str(tmp_path / 'proj/source/big.F90'),
                           str(tmp_path / 'proj/build_output/big.f90')]
        fake_process.register(process_command)

        config = BuildConfig('proj', ToolBox(), fab_workspace=tmp_path,
                             multiprocessing=False)
        config.source_root.mkdir(parents=True)
        big_f90 = Path(config.source_root / 'big.F90')
        big_f90.write_text("Big F90 file.")
        little_f90 = Path(config.source_root / 'little.f90')
        little_f90.write_text("Little f90 file.")

        def source_getter(artefact_store: ArtefactStore) -> list[Path]:
            return [big_f90, little_f90]

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            preprocess_fortran(config=config, source=source_getter)

        assert (config.build_output / 'little.f90').read_text() \
            == "Little f90 file."
        assert fake_process.call_count(process_command) == 1

    def test_wrong_exe(self, stub_tool_repository: ToolRepository,
                       tmp_path: Path,
                       fake_process: FakeProcess) -> None:
        """
        Tests detection of wrong executable.

        ToDo: Can this ever happen? Don't like messing with "private" state.
        """
        fake_process.register(['cpp', '-traditional-cpp', '-P', '--version'])
        fake_process.register(['cpp', '--version'])
        tool_box = ToolBox()
        # Take the C preprocessor
        cpp = tool_box.get_tool(Category.C_PREPROCESSOR)
        # And set its category to FORTRAN_PREPROCESSOR
        cpp._category = Category.FORTRAN_PREPROCESSOR
        # Now overwrite the Fortran preprocessor with the re-categorised
        # C preprocessor:
        tool_box.add_tool(cpp, silent_replace=True)

        config = BuildConfig('proj', tool_box, fab_workspace=tmp_path)
        with raises(RuntimeError) as err:
            preprocess_fortran(config=config)
        assert str(err.value) == "Unexpected tool 'cpp' of type '<class " \
            "'fab.tools.preprocessor.Cpp'>' instead of CppFortran"
