import os
from pathlib import Path
from unittest import mock

from fab.cli import _generic_build_config


class TestZeroConfig(object):

    def test_fortran_dependencies(self, tmp_path):
        # test the sample project in the fortran dependencies system test
        config = _generic_build_config(
            Path(__file__).parent.parent / 'FortranDependencies',
            kwargs={'fab_workspace': tmp_path, 'multiprocessing': False})
        config.run()
        assert (config.project_workspace / 'first.exe').exists()
        assert (config.project_workspace / 'second.exe').exists()

    def test_c_fortran_interop(self, tmp_path):
        # test the sample project in the fortran dependencies system test
        config = _generic_build_config(
            Path(__file__).parent.parent / 'CFortranInterop',
            kwargs={'fab_workspace': tmp_path, 'multiprocessing': False, 'verbose': True})
        config.run()
        assert (config.project_workspace / 'main.exe').exists()
