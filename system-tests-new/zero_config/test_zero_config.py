from pathlib import Path

from fab.cli import _generic_build_config


class TestZeroConfig(object):

    def test_fortran_dependencies(self, tmp_path):
        # test the sample project in the fortran dependencies system test
        config = _generic_build_config(Path(__file__).parent.parent / 'FortranDependencies', fab_workspace=tmp_path)
        config.run()
        assert (config.project_workspace / 'first.exe').exists()
        assert (config.project_workspace / 'second.exe').exists()

    def test_c_fortran_interop(self, tmp_path):
        # test the sample project in the fortran dependencies system test
        config = _generic_build_config(Path(__file__).parent.parent / 'CFortranInterop', fab_workspace=tmp_path)
        config.run()
        assert (config.project_workspace / 'main.exe').exists()
