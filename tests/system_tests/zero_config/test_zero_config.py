from pathlib import Path

from fab.cli import cli_fab


class TestZeroConfig(object):

    def test_fortran_dependencies(self, tmp_path):
        # test the sample project in the fortran dependencies system test
        kwargs = {'project_label': 'fortran deps test', 'fab_workspace': tmp_path, 'multiprocessing': False}

        config = cli_fab(
            folder=Path(__file__).parent.parent / 'FortranDependencies',
            kwargs=kwargs)

        assert (config.project_workspace / 'first.exe').exists()
        assert (config.project_workspace / 'second.exe').exists()

    def test_c_fortran_interop(self, tmp_path):
        # test the sample project in the fortran dependencies system test
        kwargs = {'project_label': 'CFInterop test', 'fab_workspace': tmp_path, 'multiprocessing': 'False'}

        config = cli_fab(
            folder=Path(__file__).parent.parent / 'CFortranInterop',
            kwargs=kwargs)

        assert (config.project_workspace / 'main.exe').exists()
