from pathlib import Path

from fab.steps.walk_source import FindSourceFiles

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFolder
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import fortran_preprocessor


class TestTinyProject(object):

    def test(self, tmp_path):
        # We want to build in a clean workspace each time the test is run.
        # (Pytest provides the tmp_path fixture.)
        self.fab_workspace = tmp_path
        print(f"fab_workspace is {self.fab_workspace}")

        self.clean_build()

        # self.no_change_rebuild()
        #
        # self.incremental_build()

    def clean_build(self):
        this_folder = Path(__file__).parent

        config = BuildConfig(
            project_label='tiny project',
            fab_workspace=self.fab_workspace,
            steps=[
                GrabFolder(this_folder / 'project-source', dst='src'),
                FindSourceFiles(),
                fortran_preprocessor(preprocessor='cpp -traditional-cpp -P'),
                Analyse(root_symbol='my_prog'),
                CompileFortran(compiler='gfortran -c', common_flags=['-J', '$output']),
                LinkExe(flags=['-lgfortran']),
            ]
        )

        config.run()

        # check it built ok

        # record the file timestamps

    def no_change_rebuild(self):
        pass

    def incremental_build(self):
        # modify the source
        pass

        # check only the right stuff has changed
