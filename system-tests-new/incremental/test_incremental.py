import logging
import zlib
from pathlib import Path
from typing import List, Dict, Set, Tuple

import pytest

from fab.build_config import BuildConfig
from fab.constants import PREBUILD
from fab.steps.analyse import Analyse
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFolder
from fab.steps.link import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.find_source_files import FindSourceFiles
from fab.util import file_walk, get_prebuild_file_groups

PROJECT_LABEL = 'tiny project'


def suffix_filter(data: Dict, suffixes: List[str]) -> Set[Tuple]:
    filtered = set(filter(lambda i: i[0].suffix in suffixes, data.items()))
    return filtered


class TestIncremental(object):
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
                CompileFortran(compiler='gfortran -c'),
                LinkExe(linker='gcc', flags=['-lgfortran']),
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

    def test_no_change_rebuild(self, build_config):
        # ensure a rebuild with no change does not recreate our prebuild artefacts

        # clean build
        clean_files, clean_timestamps, clean_hashes = self.build(build_config)

        # rebuild
        rebuild_files, rebuild_timestamps, rebuild_hashes = self.build(build_config)

        # Ensure analysis and Fortran output is unchanged.
        prebuild_files = filter(lambda p: PREBUILD in str(p), rebuild_files)
        prebuild_groups = get_prebuild_file_groups(prebuild_files)
        prebuild_folder = build_config.prebuild_folder

        self.assert_one_artefact(
            ['my_mod.*.an', 'my_mod.*.o', 'my_mod.*.mod', 'my_prog.*.an', 'my_prog.*.o'],
            prebuild_groups, prebuild_folder, clean_timestamps, clean_hashes, rebuild_timestamps, rebuild_hashes)

    def test_fortran_implementation_change(self, build_config):
        # test a code change without a module interface change

        # clean build
        clean_files, clean_timestamps, clean_hashes = self.build(build_config)

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
        rebuild_files, rebuild_timestamps, rebuild_hashes = self.build(build_config)

        # ensure the analysis and object files change but the mod file does not
        prebuild_files = filter(lambda p: PREBUILD in str(p), rebuild_files)
        prebuild_groups = get_prebuild_file_groups(prebuild_files)
        prebuild_folder = build_config.prebuild_folder

        # my_prog should be completely unaffected
        self.assert_one_artefact(
            ['my_prog.*.an', 'my_prog.*.o'],
            prebuild_groups, prebuild_folder, clean_timestamps, clean_hashes, rebuild_timestamps, rebuild_hashes)

        # my_mod will have a new mod file because the source has changed, so it's recompiled into a different artefact,
        # but the interface hasn't changed so we expect the mod contents to be identical.
        self.assert_two_identical_artefacts(
            ['my_mod.*.mod'],
            prebuild_groups, prebuild_folder, rebuild_hashes)

        self.assert_two_different_artefacts(
            ['my_mod.*.an', 'my_mod.*.o'],
            prebuild_groups, prebuild_folder, rebuild_hashes)

    def test_mod_interface_change(self, build_config):
        # test a module interface change

        # clean build
        clean_files, clean_timestamps, clean_hashes = self.build(build_config)

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
        rebuild_files, rebuild_timestamps, rebuild_hashes = self.build(build_config)

        # ensure the analysis and object files change but the mod file does not
        prebuild_files = filter(lambda p: PREBUILD in str(p), rebuild_files)
        prebuild_groups = get_prebuild_file_groups(prebuild_files)
        prebuild_folder = build_config.prebuild_folder

        # my_prog analysis should be unaffected
        self.assert_one_artefact(
            ['my_prog.*.an'],
            prebuild_groups, prebuild_folder, clean_timestamps, clean_hashes, rebuild_timestamps, rebuild_hashes)

        # We've recompiled my_prog because a mod it depends on changed.
        # That means there'll be a different version of the artefact with a new hash of things it depends on.
        # However, it's not *doing* anything different (it doesn't call the new subroutine),
        # so the object file should have the same contents.
        self.assert_two_identical_artefacts(
            ['my_prog.*.o'],
            prebuild_groups, prebuild_folder, rebuild_hashes)

        self.assert_two_different_artefacts(
            ['my_mod.*.an', 'my_mod.*.o', 'my_mod.*.mod'],
            prebuild_groups, prebuild_folder, rebuild_hashes)

    # helpers

    def build(self, build_config):
        # build the project and return the timestamps and hashes
        build_config.run()
        all_files = set(file_walk(build_config.build_output))

        timestamps = {f: f.stat().st_mtime_ns for f in all_files}
        hashes = {f: zlib.crc32(open(f, 'rb').read()) for f in all_files}
        return all_files, timestamps, hashes

    def assert_two_different_artefacts(self, pb_keys, prebuild_groups, prebuild_folder, rebuild_hashes):
        # Make sure there are two versions for each given artefact wildcard, with different contents.
        for pb in pb_keys:
            # check there's two versions of this artefact
            pb_group = prebuild_groups[pb]
            assert len(pb_group) == 2, f"expected two artefacts for {pb}"

            # check the contents changed across builds
            bob, alice = pb_group
            assert rebuild_hashes[prebuild_folder / bob] != rebuild_hashes[prebuild_folder / alice]

    def assert_two_identical_artefacts(self, pb_keys, prebuild_groups, prebuild_folder, rebuild_hashes):
        # Make sure there are two versions for each given artefact wildcard, with identical contents.
        for pb in pb_keys:
            # check there's two versions of this artefact
            pb_group = prebuild_groups[pb]
            assert len(pb_group) == 2, f"expected two artefacts for {pb}"

            # check the contents didn't change across builds
            bob, alice = pb_group
            assert rebuild_hashes[prebuild_folder / bob] == rebuild_hashes[prebuild_folder / alice]

    def assert_one_artefact(self, pb_keys, prebuild_groups, prebuild_folder,
                            clean_timestamps, clean_hashes, rebuild_timestamps, rebuild_hashes):
        # Make sure there is only one version for each given artefact wildcard.
        # Make sure the timestamp or contents weren't changed by the rebuild, meaning they weren't reprocessed.
        for pb in pb_keys:
            # check there's only one version of this artefact
            pb_group = prebuild_groups[pb]
            assert len(pb_group) == 1, f"expected one artefact for {pb}"

            # check it wasn't rebuilt
            pb_fpath = next(iter(pb_group))
            assert clean_timestamps[prebuild_folder / pb_fpath] == rebuild_timestamps[prebuild_folder / pb_fpath]
            assert clean_hashes[prebuild_folder / pb_fpath] == rebuild_hashes[prebuild_folder / pb_fpath]
