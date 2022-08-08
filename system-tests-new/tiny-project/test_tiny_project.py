import csv
from pathlib import Path

import pytest

from fab.build_config import BuildConfig
from fab.constants import BUILD_OUTPUT
from fab.steps.analyse import Analyse
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFolder
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.walk_source import FindSourceFiles, Exclude, Include
from fab.util import file_checksum

PROJECT_LABEL = 'tiny project'


class TestTinyProject(object):
    """
    Checks:
        - Basic Fortran project build
        - Incremental Fortran build

    """

    # todo: check incremental build of other file types as Fab is upgraded

    # helpers

    @pytest.fixture
    def configs(self, tmp_path):
        fab_workspace = tmp_path
        this_folder = Path(__file__).parent

        grab_config = BuildConfig(
            project_label=PROJECT_LABEL,
            fab_workspace=fab_workspace,
            steps=[
                GrabFolder(this_folder / 'project-source', dst='src'),
            ],
            multiprocessing=False,  # PyCharm on VDI can't debug with MP
        )

        build_config = BuildConfig(
            project_label=PROJECT_LABEL,
            fab_workspace=fab_workspace,
            steps=[
                FindSourceFiles(),
                fortran_preprocessor(preprocessor='cpp -traditional-cpp -P'),
                Analyse(root_symbol='my_prog'),
                CompileFortran(compiler='gfortran -c', common_flags=['-J', '$output']),
                LinkExe(flags=['-lgfortran']),
            ],
            multiprocessing=False,  # PyCharm on VDI can't debug with MP
        )

        return grab_config, build_config

    def test_clean_build(self, configs):
        grab_config, build_config = configs
        assert not (build_config.project_workspace / 'my_prog.exe').exists()

        grab_config.run()
        build_config.run()

        # check it built ok
        assert (build_config.project_workspace / 'my_prog.exe').exists()

    def build(self, build_config):

        build_config.run()

        timestamps = self.get_timestamps(build_config)
        hashes = self.get_hashes(build_config)
        csvs = self.get_csvs(build_config)

        return timestamps, hashes, csvs

    def get_timestamps(self, build_config):
        output_files = self.find_output_files(
            root=build_config.project_workspace,
            path_filters=[Exclude('log.txt', '.csv', '/metrics/', build_config.source_root)])

        timestamps = {}
        for f in output_files:
            timestamps[f] = f.stat().st_mtime_ns

        return timestamps

    def get_hashes(self, build_config):
        output_files = self.find_output_files(
            root=build_config.project_workspace,
            path_filters=[Exclude('log.txt', '.csv', '/metrics/', build_config.source_root)])

        hashes = {}
        for f in output_files:
            hashes[f] = file_checksum(f).file_hash

        return hashes

    def get_csvs(self, build_config):
        """
        Get the contents of each csv file in the project workspace.

        The row order is not deterministic so we put rows in a set for easy comparison.
        Each row is a dict, which can't go in a set. We sort and tuple the fields for easy comparison.

        """
        output_files = self.find_output_files(
            root=build_config.project_workspace,
            path_filters=[
                Exclude(build_config.project_workspace),
                Include('.csv'),
            ])

        csvs = {}
        for f in output_files:
            csvs[f] = set([tuple(sorted(row.items())) for row in csv.DictReader(open(f))])

        return csvs

    def find_output_files(self, root, path_filters):
        # might as well use this build step to find the output files, as it already does what we need
        file_finder = FindSourceFiles(
            source_root=root,
            path_filters=path_filters,
            output_collection='output files',
        )

        temp_store = {}
        file_finder.run(artefact_store=temp_store, config=None)

        return temp_store['output files']

    def test_no_change_rebuild(self, configs):
        grab_config, build_config = configs
        grab_config.run()

        # clean build
        clean_timestamps, clean_hashes, clean_csvs = self.build(build_config)

        # rebuild
        rebuild_timestamps, rebuild_hashes, rebuild_csvs = self.build(build_config)

        # make sure no Fortran compilation output has been recreated
        fortran_timestamps = set(filter(lambda i: i[0].suffix in ['.o', '.mod'], rebuild_timestamps.items()))
        assert fortran_timestamps <= set(clean_timestamps.items())
        assert rebuild_hashes == clean_hashes
        assert rebuild_csvs == clean_csvs

    def test_incremental_build_no_mod(self, configs):
        # incremental fortran build, changing module source but not interface
        grab_config, build_config = configs
        grab_config.run()

        # clean build
        clean_timestamps, clean_hashes, clean_csvs = self.build(build_config)

        # modify the fortran module source without changing the module interface
        mod_source = build_config.source_root / 'src/my_mod.F90'
        lines = open(mod_source, 'rt').readlines()
        with open(mod_source, 'wt') as out:
            for line in lines:
                out.write(line)
                # duplicate the print line
                if 'PRINT' in line:
                    out.write(line)

        # rebuild
        rebuild_timestamps, rebuild_hashes, _ = self.build(build_config)

        # check only the object file has changed, not the mod file
        build_output = build_config.project_workspace / BUILD_OUTPUT

        changed_items = set(rebuild_timestamps.items()) - set(clean_timestamps.items())
        changed_paths = [i[0] for i in changed_items]
        assert build_output / 'src/my_mod.o' in changed_paths
        assert build_output / 'my_mod.mod' not in changed_paths

    def test_incremental_build_mod(self, configs):
        # incremental fortran build, changing module including interface
        grab_config, build_config = configs
        grab_config.run()

        # clean build
        clean_timestamps, clean_hashes, clean_csvs = self.build(build_config)

        # modify the fortran module source, changing the module interface
        mod_source = build_config.source_root / 'src/my_mod.F90'
        lines = open(mod_source, 'rt').readlines()
        with open(mod_source, 'wt') as out:
            for line in lines:
                out.write(line)
                # add an extra subroutine
                if 'END SUBROUTINE' in line:
                    out.write("""
                        SUBROUTINE added_func ()
                        
                            INTEGER :: bar = 2
                            PRINT *, bar
                        
                        END SUBROUTINE added_func                    
                    """)

        # rebuild
        rebuild_timestamps, rebuild_hashes, _ = self.build(build_config)

        # check both the object file and mod file have changed
        build_output = build_config.project_workspace / BUILD_OUTPUT

        changed_items = set(rebuild_timestamps.items()) - set(clean_timestamps.items())
        changed_paths = [i[0] for i in changed_items]
        assert build_output / 'src/my_mod.o' in changed_paths
        assert build_output / 'my_mod.mod' in changed_paths
