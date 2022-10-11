import csv
import logging
import zlib
from pathlib import Path
from typing import Iterable

import pytest

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse, ANALYSIS_CSV
from fab.steps.compile_fortran import CompileFortran, FORTRAN_COMPILED_CSV
from fab.steps.grab import GrabFolder
from fab.steps.link import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.find_source_files import FindSourceFiles
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

        # Only the analysis csv hash is allowed to change, because it stores sets.
        # We check below that the contents are equivalent.
        changed_hashes = dict(set(rebuild_hashes.items()) - set(clean_hashes.items()))
        assert set(changed_hashes.keys()) - {build_config.build_output / ANALYSIS_CSV, } == set()

        # csv contents should not have changed
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

        # ensure the object file, but not the mod file, changes timestamp
        changed_timestamps = dict(set(rebuild_timestamps.items()) - set(clean_timestamps.items()))
        allowed_timestamp_changes = {
            build_config.build_output / 'src/my_prog.f90',
            build_config.build_output / 'src/my_mod.f90',
            build_config.build_output / 'src/my_mod.o',
            build_config.build_output / ANALYSIS_CSV,
            build_config.build_output / FORTRAN_COMPILED_CSV,
        }
        assert set(changed_timestamps.keys()) - allowed_timestamp_changes == set()

        # ensure the object file, but not the mod file, changes hash
        changed_hashes = dict(set(rebuild_hashes.items()) - set(clean_hashes.items()))
        allowed_hash_changes = {
            build_config.build_output / 'src/my_mod.f90',
            build_config.build_output / 'src/my_mod.o',
            build_config.build_output / ANALYSIS_CSV,
            build_config.build_output / FORTRAN_COMPILED_CSV,
        }
        assert set(changed_hashes.keys()) - allowed_hash_changes == set()

        # The analysis csv should have some changes...
        clean_analysis_csv = clean_csvs[build_config.build_output / ANALYSIS_CSV]
        rebuild_analysis_csv = rebuild_csvs[build_config.build_output / ANALYSIS_CSV]
        changed_analysis_csv = rebuild_analysis_csv - clean_analysis_csv
        # ...one row, for my_mod.f90
        assert len(changed_analysis_csv) == 1
        assert dict(changed_analysis_csv.pop())['fpath'] == str(build_config.build_output / 'src/my_mod.f90')

        # The fortran csv should have some changes...
        clean_fortran_csv = clean_csvs[build_config.build_output / FORTRAN_COMPILED_CSV]
        rebuild_fortran_csv = rebuild_csvs[build_config.build_output / FORTRAN_COMPILED_CSV]
        changed_fortran_csv = rebuild_fortran_csv - clean_fortran_csv
        # ...one row, for my_mod.f90
        assert len(changed_fortran_csv) == 1
        assert dict(changed_fortran_csv.pop())['input_fpath'] == str(build_config.build_output / 'src/my_mod.f90')

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

        # ensure both the object file and mod file have changed timestamps
        changed_timestamps = dict(set(rebuild_timestamps.items()) - set(clean_timestamps.items()))
        allowed_timestamp_changes = {
            build_config.build_output / 'src/my_prog.f90',
            build_config.build_output / 'src/my_prog.o',
            build_config.build_output / 'src/my_mod.f90',
            build_config.build_output / 'src/my_mod.o',
            build_config.build_output / 'my_mod.mod',
            build_config.build_output / ANALYSIS_CSV,
            build_config.build_output / FORTRAN_COMPILED_CSV,
        }
        assert set(changed_timestamps.keys()) - allowed_timestamp_changes == set()

        # ensure the object file, but not the mod file, changes hash
        changed_hashes = dict(set(rebuild_hashes.items()) - set(clean_hashes.items()))
        allowed_hash_changes = {
            build_config.build_output / 'src/my_prog.o',
            build_config.build_output / 'src/my_mod.f90',
            build_config.build_output / 'src/my_mod.o',
            build_config.build_output / 'my_mod.mod',
            build_config.build_output / ANALYSIS_CSV,
            build_config.build_output / FORTRAN_COMPILED_CSV,
        }
        assert set(changed_hashes.keys()) - allowed_hash_changes == set()

        # The analysis csv should only have changes for the single changed source file
        clean_analysis_csv = clean_csvs[build_config.build_output / ANALYSIS_CSV]
        rebuild_analysis_csv = rebuild_csvs[build_config.build_output / ANALYSIS_CSV]
        changed_analysis_csv = rebuild_analysis_csv - clean_analysis_csv
        assert len(changed_analysis_csv) == 1

        # The compilation csv should have changes for both files because it includes dependency hashes
        clean_fortran_csv = clean_csvs[build_config.build_output / FORTRAN_COMPILED_CSV]
        rebuild_fortran_csv = rebuild_csvs[build_config.build_output / FORTRAN_COMPILED_CSV]
        changed_fortran_csv = rebuild_fortran_csv - clean_fortran_csv
        assert len(changed_fortran_csv) == 2
