from pathlib import Path

import pytest

from fab.cli import cli_fab
from fab.tools import ToolRepository


class TestZeroConfig():

    def test_fortran_dependencies(self, tmp_path):
        # test the sample project in the fortran dependencies system test
        with pytest.warns(DeprecationWarning, match="RootIncFiles is deprecated as .inc files are due to be removed."):
            kwargs = {'project_label': 'fortran deps test', 'fab_workspace': tmp_path, 'multiprocessing': False}

            config = cli_fab(
                folder=Path(__file__).parent.parent / 'FortranDependencies',
                kwargs=kwargs)

            assert (config.project_workspace / 'first').exists()
            assert (config.project_workspace / 'second').exists()

    def test_c_fortran_interop(self, tmp_path):
        # test the sample project in the fortran dependencies system test
        with pytest.warns(DeprecationWarning, match="RootIncFiles is deprecated as .inc files are due to be removed."):
            kwargs = {'project_label': 'CFInterop test', 'fab_workspace': tmp_path, 'multiprocessing': 'False'}

            config = cli_fab(
                folder=Path(__file__).parent.parent / 'CFortranInterop',
                kwargs=kwargs)

            assert (config.project_workspace / 'main').exists()

    def test_fortran_explicit_gfortran(self, tmp_path):
        # test the sample project in the fortran dependencies system test
        kwargs = {'project_label': 'fortran explicit gfortran', 'fab_workspace': tmp_path, 'multiprocessing': False}

        tr = ToolRepository()
        tr.set_default_vendor("gnu")

        # TODO: If the intel compiler should be used here, the linker will
        # need an additional flag (otherwise duplicated `main` symbols will
        # occur). The following code can be used e.g. in cli.py:
        #
        # if config.tool_box.get_tool(Categories.LINKER).name == "linker-ifort":
        #    flags = ["-nofor-main"]

        with pytest.warns(DeprecationWarning, match="RootIncFiles is deprecated as .inc files are due to be removed."):
            config = cli_fab(
                folder=Path(__file__).parent.parent / 'CFortranInterop',
                kwargs=kwargs)

        assert (config.project_workspace / 'main').exists()
