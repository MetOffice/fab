import logging
from pathlib import Path
from unittest import mock

import pytest
from fab.util import file_walk, file_checksum

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFolder, GrabPreBuild
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.walk_source import FindSourceFiles


class TestFortranPrebuild(object):

    def build_config(self, fab_workspace, prebuild_folder=None):
        logging.getLogger('fab').setLevel(logging.WARNING)

        build_config = BuildConfig(
            project_label='test_prebuild',
            fab_workspace=fab_workspace,
            steps=[
                GrabFolder(Path(__file__).parent / 'project-source', dst='src'),
                *([GrabPreBuild(prebuild_folder)] if prebuild_folder else []),
                FindSourceFiles(),
                fortran_preprocessor(preprocessor='cpp -traditional-cpp -P'),
                Analyse(root_symbol='my_prog'),
                CompileFortran(compiler='gfortran -c', common_flags=['-J', '$output']),
                LinkExe(flags=['-lgfortran']),
            ],
            multiprocessing=False,
        )

        return build_config

    def test_vanilla(self, tmp_path):
        # share a prebuild from a different folder

        # build the project in "some other fab workspace", from where we'll share its prebuild
        other_config = self.build_config(fab_workspace=tmp_path / 'other_workspace')
        other_config.run()

        # now build the project in our workspace
        my_config = self.build_config(fab_workspace=tmp_path / 'my_workspace',
                                      prebuild_folder=other_config.prebuild_folder)

        # make sure we don't call the compiler at all this time
        with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
            my_config.run()
        mock_compile_file.assert_not_called()

        # make sure the exe was built
        exe = my_config.project_workspace / 'my_prog.exe'
        assert exe.exists()
