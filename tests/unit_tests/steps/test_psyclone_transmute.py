# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

"""
Tests the PSyclone transmutation step in Fab. It requires PSyclone to
be available (otherwise the tests will be skipped).
"""

from pathlib import Path
import shutil
from unittest.mock import MagicMock, patch
import warnings

from pytest import fixture, mark, warns

from fab.build_config import BuildConfig
from fab.artefacts import ArtefactStore, ArtefactSet
from fab.steps.psyclone_transmute import psyclone_transmute, MpCommonArgs
from fab.tools.psyclone import Psyclone
from fab.tools.tool_box import ToolBox


@fixture
def config(tmp_path):
    """
    Create a fake workspace with input Fortran files.
    """
    src = tmp_path / "src"
    src.mkdir()
    f1 = src / "a.f90"
    f2 = src / "b.f90"
    f1.write_text("program a\nend program")
    f2.write_text("program b\nend program")
    cfg = BuildConfig(project_label="test",
                      fab_workspace=tmp_path,
                      tool_box=ToolBox())
    cfg.artefact_store.add(ArtefactSet.FORTRAN_COMPILER_FILES, [f1, f2])
    return cfg

@mark.skipif(not Psyclone().is_available, reason="psyclone cli tool not available")
def test_psyclone_transmute_basic(config):
    """
    Test basic behaviour, without changing any artefact set
    """

    input_files = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]
    # Make a copy to ensure changes to artefact store will be detected
    input_files = input_files.copy()

    # Expected files will be in the build output directory and
    # have the new suffix `_transmute` added.
    expected = {config.build_output / '/'.join(i.parts[1:])
                for i in input_files}
    expected = {i.with_stem(i.stem + "_transmute") for i in expected}

    with warns(UserWarning,
               match="_metric_send_conn not set, cannot send metrics"):
        psyclone_transmute(
            config,
            input_files)
    assert config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES] == input_files



@mark.skipif(not Psyclone().is_available, reason="psyclone cli tool not available")
def test_psyclone_transmute_artefact_set(config):

    input_files = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]

    # Expected files will be in the build output directory and
    # have the new suffix `_transmute` added.
    expected = {config.build_output / '/'.join(i.parts[1:])
                for i in input_files}
    expected = {i.with_stem(i.stem + "_transmute") for i in expected}

    with warns(UserWarning,
               match="_metric_send_conn not set, cannot send metrics"):
        psyclone_transmute(
            config,
            config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES],
            artefact_set=ArtefactSet.FORTRAN_COMPILER_FILES)
    output_files = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]

    assert expected == output_files
    #transmuted_input_files = set(i.)
    return




    # Fake output directory
    out_dir = tmp / "build"
    out_dir.mkdir()


    psyclone_transmute(config=config)

    # --- Assertions ---

    # run_mp called with correct number of jobs
    assert mp_mock.called
    args, kwargs = mp_mock.call_args
    _, mp_arg, func = args
    assert func.__name__ == "transmute_one_file"
    assert len(mp_arg) == len(fortran_files)

    # Output files added to artefact store
    stored = config.artefact_store.get(ArtefactSet.FORTRAN_COMPILER_FILES)
    assert len(stored) == len(fortran_files)
    for f in stored:
        assert f.suffix == ".f90"
        assert f.stem.endswith("_transmute")

    # Prebuilds recorded
    assert len(config.current_prebuilds) == len(fortran_files)

    # check_for_errors called
    assert check_mock.called


