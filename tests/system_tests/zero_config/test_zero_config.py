##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
This module test zero config.
"""

from pathlib import Path
from shutil import copytree

import pytest

from fab.cli import cli_fab


class TestZeroConfig:
    """
    Exercises "zero configuration" mode.
    """
    def test_fortran(self, tmp_path: Path) -> None:
        """
        Tests a sample Fortran source.

        ToDo: Fragile due to assumption of donor code.
        """
        copytree(
            Path(__file__).parent.parent / 'FortranDependencies' /
            'project-source',
            tmp_path / 'source'
        )

        kwargs = {'project_label': 'fortran test',
                  'fab_workspace': tmp_path,
                  'multiprocessing': False}

        config = cli_fab(folder=tmp_path / 'source', kwargs=kwargs)

        assert (config.project_workspace / 'first').exists()
        assert (config.project_workspace / 'second').exists()

    def test_c(self, tmp_path: Path) -> None:
        """
        Tests a sample C project.

        ToDo: Fragility due to assumption of source donor.
        """
        pytest.importorskip('clang', reason="Missing libclang bindings.")
        copytree(
            Path(__file__).parent.parent / 'CUserHeader' / 'project-source',
            tmp_path / 'source'
        )

        kwargs = {'project_label': 'c test',
                  'fab_workspace': tmp_path,
                  'multiprocessing': False}
        config = cli_fab(folder=tmp_path / 'source', kwargs=kwargs)
        assert (config.project_workspace / 'main').exists()

    def test_c_fortran(self, tmp_path: Path) -> None:
        """
        Tests a sample C project which interworks with Fortran.

        ToDo: Fragility due to assumption of source donor.
        """
        pytest.importorskip('clang', reason="Missing libclang bindings.")
        copytree(
            Path(__file__).parent.parent / 'CFortranInterop' /
            'project-source', tmp_path / 'source'
        )

        kwargs = {'project_label': 'C test',
                  'fab_workspace': tmp_path / 'fab',
                  'multiprocessing': False}
        config = cli_fab(folder=tmp_path / 'source', kwargs=kwargs)
        assert (config.project_workspace / 'main').exists()
