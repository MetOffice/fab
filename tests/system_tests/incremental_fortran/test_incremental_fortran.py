import logging
import os
import zlib
from datetime import timedelta, datetime
from pathlib import Path

import pytest

from fab.build_config import BuildConfig
from fab.constants import PREBUILD, CURRENT_PREBUILDS, BUILD_OUTPUT
from fab.steps.analyse import analyse
from fab.steps.cleanup_prebuilds import cleanup_prebuilds
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files
from fab.steps.grab.folder import grab_folder
from fab.steps.link import link_exe
from fab.steps.preprocess import preprocess_fortran
from fab.tools import ToolBox
from fab.util import file_walk, get_prebuild_file_groups

PROJECT_LABEL = 'tiny_project'


class TestIncremental(object):
    """
    Checks:
        - basic Fortran project build
        - incremental Fortran build, with and without mod changes

    Each test runs in a different fab workspace each time, with a rolling history kept of the last three runs.

    """

    # todo: check incremental build of other file types as Fab is upgraded

    @pytest.fixture
    def config(self, tmp_path):  # tmp_path is a pytest fixture which differs per test, per run
        logging.getLogger('fab').setLevel(logging.WARNING)

        with BuildConfig(project_label=PROJECT_LABEL,
                         tool_box=ToolBox(), fab_workspace=tmp_path,
                         multiprocessing=False) as grab_config:
            grab_folder(grab_config, Path(__file__).parent / 'project-source', dst_label='src')

        build_config = BuildConfig(project_label=PROJECT_LABEL,
                                   tool_box=ToolBox(), fab_workspace=tmp_path,
                                   multiprocessing=False)

        return build_config

    def run_steps(self, build_config):
        find_source_files(build_config)
        preprocess_fortran(build_config)
        analyse(build_config, root_symbol='my_prog')
        compile_fortran(build_config)
        link_exe(build_config, flags=['-lgfortran'])
        # Add a permissive cleanup step because we want to know about every file which is created,
        # across multiple runs of the build. Otherwise, an aggressive cleanup will be automatically added.
        cleanup_prebuilds(build_config, older_than=timedelta(weeks=1))

    def test_clean_build(self, config):
        # just make sure an exe appears
        assert not (config.project_workspace / 'my_prog').exists()

        with config:
            self.run_steps(config)

        # check it built ok
        assert (config.project_workspace / 'my_prog').exists()

    def test_no_change_rebuild(self, config):
        # ensure a rebuild with no change does not recreate our prebuild artefacts

        # clean build
        clean_files, clean_timestamps, clean_hashes = self.build(config)

        # rebuild
        rebuild_files, rebuild_timestamps, rebuild_hashes = self.build(config)

        # Ensure analysis and Fortran output is unchanged.
        prebuild_files = filter(lambda p: PREBUILD in str(p), rebuild_files)
        prebuild_groups = get_prebuild_file_groups(prebuild_files)
        prebuild_folder = config.prebuild_folder

        self.assert_one_artefact(
            ['my_mod.*.an', 'my_mod.*.o', 'my_mod.*.mod', 'my_prog.*.an', 'my_prog.*.o'],
            prebuild_groups, prebuild_folder, clean_timestamps, clean_hashes, rebuild_timestamps, rebuild_hashes)

    def test_fortran_implementation_change(self, config):
        # test a code change without a module interface change

        # clean build
        clean_files, clean_timestamps, clean_hashes = self.build(config)

        # modify the fortran module source without changing the module interface
        mod_source = config.source_root / 'src/my_mod.F90'
        lines = open(mod_source, 'rt').readlines()
        with open(mod_source, 'wt') as out:
            for line in lines:
                out.write(line)
                # duplicate the print line
                if 'PRINT' in line:
                    out.write(line)

        # rebuild
        rebuild_files, rebuild_timestamps, rebuild_hashes = self.build(config)

        # ensure the analysis and object files change but the mod file does not
        prebuild_files = filter(lambda p: PREBUILD in str(p), rebuild_files)
        prebuild_groups = get_prebuild_file_groups(prebuild_files)
        prebuild_folder = config.prebuild_folder

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

    def test_mod_interface_change(self, config):
        # test a module interface change

        # clean build
        clean_files, clean_timestamps, clean_hashes = self.build(config)

        # modify the fortran module source, changing the module interface
        mod_source = config.source_root / 'src/my_mod.F90'
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
        rebuild_files, rebuild_timestamps, rebuild_hashes = self.build(config)

        # ensure the analysis and object files change but the mod file does not
        prebuild_files = filter(lambda p: PREBUILD in str(p), rebuild_files)
        prebuild_groups = get_prebuild_file_groups(prebuild_files)
        prebuild_folder = config.prebuild_folder

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
        with build_config:
            self.run_steps(build_config)

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


class TestCleanupPrebuilds(object):
    # Test cleanup of the incremental build artefacts

    in_out = [
        # prune artefacts by age
        ({'older_than': timedelta(days=15)}, ['a.123.foo', 'a.234.foo']),
        ({'older_than': timedelta(days=25)}, ['a.123.foo', 'a.234.foo', 'a.345.foo']),

        # prune individual artefact versions (hashes) by age
        ({'n_versions': 2}, ['a.123.foo', 'a.234.foo']),
        ({'n_versions': 3}, ['a.123.foo', 'a.234.foo', 'a.345.foo']),

        # pruning a file which is covered by both the age and the version pruning code.
        # this is to protect against trying to delete a non-existent file.
        ({'older_than': timedelta(days=15), 'n_versions': 2}, ['a.123.foo', 'a.234.foo']),
    ]

    @pytest.mark.parametrize("kwargs,expect", in_out)
    def test_clean(self, tmp_path, kwargs, expect):

        with BuildConfig(project_label=PROJECT_LABEL,
                         tool_box=ToolBox(),
                         fab_workspace=tmp_path, multiprocessing=False) as config:
            remaining = self._prune(config, kwargs=kwargs)

        assert sorted(remaining) == expect

    def test_prune_unused(self, tmp_path):
        # pruning everything not current

        with BuildConfig(project_label=PROJECT_LABEL,
                         tool_box=ToolBox(), fab_workspace=tmp_path,
                         multiprocessing=False) as config:
            config._artefact_store = {CURRENT_PREBUILDS: {
                tmp_path / PROJECT_LABEL / BUILD_OUTPUT / PREBUILD / 'a.123.foo',
                tmp_path / PROJECT_LABEL / BUILD_OUTPUT / PREBUILD / 'a.456.foo',
            }}

            remaining = self._prune(config, kwargs={'all_unused': True})

        assert sorted(remaining) == [
            'a.123.foo',
            'a.456.foo',
        ]

    def _prune(self, config, kwargs):

        # create several versions of the same artefact
        artefacts = [
            ('a.123.foo', datetime(2022, 10, 31)),
            ('a.234.foo', datetime(2022, 10, 21)),
            ('a.345.foo', datetime(2022, 10, 11)),
            ('a.456.foo', datetime(2022, 10, 1)),
        ]
        for a, t in artefacts:
            path = config.prebuild_folder / a
            path.touch(exist_ok=False)
            os.utime(path, (t.timestamp(), t.timestamp()))

        cleanup_prebuilds(config, **kwargs)

        remaining_artefacts = file_walk(config.prebuild_folder)
        # pull out just the filenames so we can parameterise the tests without knowing tmp_path
        remaining_artefacts = [str(f.name) for f in remaining_artefacts]
        return remaining_artefacts
