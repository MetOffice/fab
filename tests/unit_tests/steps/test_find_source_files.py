##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Test the find_source_files step.
"""

from pathlib import Path

import pytest

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps.find_source_files import Exclude, find_source_files, Include
from fab.tools.tool_box import ToolBox


@pytest.fixture(name="setup_files")
def setup_files_fixture(tmp_path: Path) -> set[Path]:
    """
    Sets up some dummy files and directories in tmp_path
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "nested").mkdir()

    files = set([
        src / "a.f90",
        src / "b.F90",
        src / "nested" / "c.c",
        src / "psy_file.x90",
    ])

    for f in files:
        f.write_text("program test\nend program")
    return files


def test_find_source_files_all_files(setup_files: set[Path],
                                     tmp_path: Path):
    """
    Ensure find_source_files walks the directory tree and returns all files.
    Also check that Fortran, C and X90 files are detected as expected and
    put in the right artefact store.
    """
    config = BuildConfig('proj', ToolBox(),
                         fab_workspace=Path(tmp_path / 'fab'))

    with pytest.warns(UserWarning, match="_metric_send_conn not set, "):
        find_source_files(config, source_root=tmp_path)

    artefacts = config.artefact_store[ArtefactSet.INITIAL_SOURCE_FILES]
    assert setup_files == artefacts

    src = tmp_path / "src"
    artefacts = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]
    assert set([src / "a.f90", src / "b.F90"]) == artefacts

    artefacts = config.artefact_store[ArtefactSet.C_COMPILER_FILES]
    assert set([src / "nested" / "c.c"]) == artefacts

    artefacts = config.artefact_store[ArtefactSet.X90_COMPILER_FILES]
    assert set([src / "psy_file.x90"]) == artefacts


def test_find_source_files_collection(setup_files: set[Path],
                                      tmp_path: Path):
    """
    Check that the default artefact set can be set.
    """
    config = BuildConfig('proj', ToolBox(),
                         fab_workspace=Path(tmp_path / 'fab'))

    with pytest.warns(UserWarning, match="_metric_send_conn not set, "):
        find_source_files(config,
                          output_collection=ArtefactSet.CURRENT_PREBUILDS,
                          source_root=tmp_path)

    assert set() == config.artefact_store[ArtefactSet.INITIAL_SOURCE_FILES]
    artefacts = config.artefact_store[ArtefactSet.CURRENT_PREBUILDS]
    assert setup_files == artefacts


def test_find_source_files_exclude(setup_files: set[Path],
                                   tmp_path: Path):
    """
    Ensure find_source_files uses exclude flags as expected.
    """
    config = BuildConfig('proj', ToolBox(),
                         fab_workspace=Path(tmp_path / 'fab'))
    path_filters = [Exclude("a.f90", "b.F90")]
    with pytest.warns(UserWarning, match="_metric_send_conn not set, "):
        find_source_files(config,
                          source_root=tmp_path,
                          path_filters=path_filters)

    artefacts = config.artefact_store[ArtefactSet.INITIAL_SOURCE_FILES]
    remaining_files = setup_files
    remaining_files.remove(tmp_path / "src" / "a.f90")
    remaining_files.remove(tmp_path / "src" / "b.F90")
    assert remaining_files == artefacts


def test_find_source_files_exclude_include(setup_files: set[Path],
                                           tmp_path: Path):
    """
    Ensure find_source_files uses exclude and include flags as expected.
    """
    config = BuildConfig('proj', ToolBox(),
                         fab_workspace=Path(tmp_path / 'fab'))
    # The first will exclude src/b.F90 (see previous test), the
    # later include will allow it in
    path_filters = [Exclude("a.f90", "b.F90"), Include("src/b.F90")]
    # Check the __str__ functions as well:
    assert str(path_filters[0]) == "Exclude(a.f90, b.F90)"
    assert str(path_filters[1]) == "Include(src/b.F90)"
    with pytest.warns(UserWarning, match="_metric_send_conn not set, "):
        find_source_files(config,
                          source_root=tmp_path,
                          path_filters=path_filters)

    remaining_files = setup_files
    remaining_files.remove(tmp_path / "src" / "a.f90")

    artefacts = config.artefact_store[ArtefactSet.INITIAL_SOURCE_FILES]
    assert remaining_files == artefacts


def test_find_source_files_longest_match(setup_files: set[Path],
                                         tmp_path: Path):
    """
    Ensure find_source_files uses exclude and include flags matching
    with the longest match.
    """
    config = BuildConfig('proj', ToolBox(),
                         fab_workspace=Path(tmp_path / 'fab'))
    # The first will exclude src/b.F90 (see previous test), the
    # later include is shorter (as opposed to the previous test
    # which used src/b.F90and so must be ignored
    path_filters = [Exclude("a.f90", "b.F90"), Include("rc/b")]
    with pytest.warns(UserWarning, match="_metric_send_conn not set, "):
        find_source_files(config,
                          source_root=tmp_path,
                          path_filters=path_filters)

    # Since the include uses a shorter pattern, it will be ignored
    # and so the Exclude will also remove b.F90
    remaining_files = setup_files
    remaining_files.remove(tmp_path / "src" / "a.f90")
    remaining_files.remove(tmp_path / "src" / "b.F90")

    artefacts = config.artefact_store[ArtefactSet.INITIAL_SOURCE_FILES]
    assert remaining_files == artefacts


@pytest.mark.usefixtures("setup_files")
def test_find_source_files_no_files(tmp_path: Path):
    """
    Ensure find_source_files walks the directory tree and returns only files
    matching the configured extensions.
    """
    config = BuildConfig('proj', ToolBox(),
                         fab_workspace=Path(tmp_path / 'fab'))
    path_filters = [Exclude("src")]
    with pytest.raises(RuntimeError) as err:
        find_source_files(config,
                          source_root=tmp_path,
                          path_filters=path_filters)
    assert "no source files found after filtering" in str(err.value)

    artefacts = config.artefact_store[ArtefactSet.INITIAL_SOURCE_FILES]
    assert set() == artefacts
