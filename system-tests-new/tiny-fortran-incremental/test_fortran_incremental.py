import csv
import logging
import zlib
from pathlib import Path
from typing import Iterable

import pytest

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse, ANALYSIS_CSV
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFolder
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.walk_source import FindSourceFiles
from fab.util import file_walk

PROJECT_LABEL = 'tiny project'


class TestFortranIncremental(object):
    """
    Checks:
        - basic Fortran project build
        - incremental Fortran build, with and without mod changes

    Each test runs in a different fab workspace each time, with a rolling history kept of the last three runs.

    """

    # todo: check incremental build of other file types as Fab is upgraded

    @pytest.fixture
    def build_config(self, tmp_path):  # tmp_path is a pytest fixture which differs per test, per run
        logging.getLogger('fab').setLevel(logging.WARNING)

        grab_config = BuildConfig(
            project_label=PROJECT_LABEL,
            fab_workspace=tmp_path,
            steps=[
                GrabFolder(Path(__file__).parent / 'project-source', dst='src'),
            ],
            multiprocessing=False,
        )
        grab_config.run()

        build_config = BuildConfig(
            project_label=PROJECT_LABEL,
            fab_workspace=tmp_path,
            steps=[
                FindSourceFiles(),
                fortran_preprocessor(preprocessor='cpp -traditional-cpp -P'),
                Analyse(root_symbol='my_prog'),
                CompileFortran(compiler='gfortran -c', common_flags=['-J', '$output']),
                LinkExe(flags=['-lgfortran']),
            ],
            multiprocessing=False,
        )

        return build_config

    def test_clean_build(self, build_config):
        # just make sure an exe appears
        assert not (build_config.project_workspace / 'my_prog.exe').exists()

        build_config.run()

        # check it built ok
        assert (build_config.project_workspace / 'my_prog.exe').exists()

    def build(self, build_config):

        build_config.run()

        all_files = set(file_walk(build_config.build_output))
        timestamps = {f: f.stat().st_mtime_ns for f in all_files}
        hashes = {f: zlib.crc32(open(f, 'rb').read()) for f in all_files}

        csvs = self.get_csvs(all_files)

        return timestamps, hashes, csvs

    def get_csvs(self, all_files: Iterable[Path]):
        """
        Get the contents of each csv file in the project workspace.

        The row order is not deterministic so we put rows in a set for easy comparison.
        Each row is a dict, which can't go in a set, so we sort and tuple row items for easy comparison.

        """
        csvs = {}
        for f in all_files:
            if f.suffix == '.csv':
                csvs[f] = set([tuple(sorted(row.items())) for row in csv.DictReader(open(f))])

        return csvs

    def test_no_change_rebuild(self, build_config):
        # ensure a rebuild with no changes does not recompile any fortran

        # clean build
        clean_timestamps, clean_hashes, clean_csvs = self.build(build_config)

        # rebuild
        rebuild_timestamps, rebuild_hashes, rebuild_csvs = self.build(build_config)

        # ensure timestamps of Fortran compiler output are unchanged
        fortran_timestamps = set(filter(lambda i: i[0].suffix in ['.o', '.mod'], rebuild_timestamps.items()))
        assert fortran_timestamps <= set(clean_timestamps.items())

        # The analysis csv hash is allowed to change, because it stores sets.
        # We check below that the contents are equivalent.
        changed_hashes = dict(set(rebuild_hashes.items()) - set(clean_hashes.items()))
        assert set(changed_hashes.keys()) - {build_config.build_output / ANALYSIS_CSV, } == set()

        # csv contents should not have changed beyond set order
        assert rebuild_csvs == clean_csvs

    def test_mod_implementation_only_change(self, build_config):
        # test incremental fortran build, code change but no module change

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
        rebuild_timestamps, rebuild_hashes, rebuild_csvs = self.build(build_config)

        # ensure my_prog still only has one object file, and the timestamp hasn't changed
        my_prog_clean_objs = {k: v for k, v in clean_timestamps.items() if 'my_prog' in str(k) and k.suffix == '.o'}
        my_prog_rebuild_objs = {k: v for k, v in rebuild_timestamps.items() if 'my_prog' in str(k) and k.suffix == '.o'}
        assert my_prog_clean_objs == my_prog_rebuild_objs
        assert len(my_prog_rebuild_objs) == 1

        # ensure the mod file doesn't change hash
        assert clean_hashes[build_config.build_output / 'my_mod.mod'] == \
               rebuild_hashes[build_config.build_output / 'my_mod.mod']

        # The analysis csv should have some changes...
        clean_analysis_csv = clean_csvs[build_config.build_output / ANALYSIS_CSV]
        rebuild_analysis_csv = rebuild_csvs[build_config.build_output / ANALYSIS_CSV]
        changed_analysis_csv = rebuild_analysis_csv - clean_analysis_csv
        # ...one row, for my_mod.f90
        assert len(changed_analysis_csv) == 1
        assert dict(changed_analysis_csv.pop())['fpath'] == str(build_config.build_output / 'src/my_mod.f90')

    def test_mod_interface_change(self, build_config):
        # test incremental fortran build with module change

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
        rebuild_timestamps, rebuild_hashes, rebuild_csvs = self.build(build_config)

        # ensure my_prog now has an extra object file
        expect_first_obj = Path(build_config.prebuild_folder / 'my_prog.1a07264d8.o')
        expect_second_obj = Path(build_config.prebuild_folder / 'my_prog.12d6465f2.o')

        assert expect_first_obj in clean_timestamps
        assert expect_second_obj not in clean_timestamps

        assert expect_first_obj in rebuild_timestamps
        assert expect_second_obj in rebuild_timestamps

        # ensure the mod file hash changed
        assert clean_hashes[build_config.build_output / 'my_mod.mod'] != \
               rebuild_hashes[build_config.build_output / 'my_mod.mod']

        # The analysis csv should only have changes for the single changed source file
        clean_analysis_csv = clean_csvs[build_config.build_output / ANALYSIS_CSV]
        rebuild_analysis_csv = rebuild_csvs[build_config.build_output / ANALYSIS_CSV]
        changed_analysis_csv = rebuild_analysis_csv - clean_analysis_csv
        assert len(changed_analysis_csv) == 1
