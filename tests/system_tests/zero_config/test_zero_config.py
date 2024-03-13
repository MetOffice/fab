from pathlib import Path

from fab.cli import cli_fab
import shutil
import os
from unittest import mock

import pytest


class TestZeroConfig(object):

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

        cc = shutil.which('gcc')
        fc = shutil.which('gfortran')

        with mock.patch.dict(os.environ, CC=cc, FC=fc, LD=fc), \
             pytest.warns(DeprecationWarning, match="RootIncFiles is deprecated as .inc files are due to be removed."):
            config = cli_fab(
                folder=Path(__file__).parent.parent / 'CFortranInterop',
                kwargs=kwargs)

        assert (config.project_workspace / 'main').exists()
