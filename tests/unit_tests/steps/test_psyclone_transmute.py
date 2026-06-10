# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

"""
Tests the PSyclone transmutation step in Fab. It requires PSyclone to
be available (otherwise the tests will be skipped).
"""

from pytest import CaptureFixture, fixture, mark, raises, warns

from fab.build_config import BuildConfig
from fab.artefacts import ArtefactSet
from fab.steps.psyclone_transmute import psyclone_transmute
from fab.tools.psyclone import Psyclone
from fab.tools.tool_box import ToolBox


@fixture(name="config")
def config_fixture(tmp_path):
    """
    Create a fake workspace with input Fortran files.
    """
    src = tmp_path / "src"
    src.mkdir()
    f1 = src / "a.f90"
    f2 = src / "b.f90"
    f1.write_text("program a\nend program")
    f2.write_text("program b\nend program")
    override = tmp_path / "override"
    override.mkdir()
    f1_override = override / "a.f90"
    f1_override.write_text("program overwrite_a\nend program")
    cfg = BuildConfig(project_label="test",
                      fab_workspace=tmp_path,
                      tool_box=ToolBox(),
                      multiprocessing=False,
                      )
    cfg.artefact_store.add(ArtefactSet.FORTRAN_COMPILER_FILES, [f1, f2])
    return cfg


@mark.skipif(not Psyclone().is_available,
             reason="psyclone cli tool not available")
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

    with (warns(UserWarning,
                match="_metric_send_conn not set, cannot send metrics"),
          warns(UserWarning,
                match="No transformation script specified")):
        psyclone_transmute(
            config,
            input_files)

    input_files = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]

    # Expected files will be in the build output directory and
    # have the new suffix `_transmute` added.
    expected = {config.build_output / '/'.join(i.parts[1:])
                for i in input_files}
    expected = {i.with_stem(i.stem + "_transmute") for i in expected}

    # Since we didn't specify ... XXXXXXXXXX
    assert (config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES] ==
            input_files)


@mark.skipif(not Psyclone().is_available,
             reason="psyclone cli tool not available")
def test_psyclone_transmute_artefact_set(config):
    """
    Verifies that we get the expected updated artefact set.
    """

    input_files = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]

    # Expected files will be in the build output directory and
    # have the new suffix `_transmute` added.
    expected = {config.build_output / '/'.join(i.parts[1:])
                for i in input_files}
    expected = {i.with_stem(i.stem + "_transmute") for i in expected}

    with (warns(UserWarning,
                match="_metric_send_conn not set, cannot send metrics"),
          warns(UserWarning,
                match="No transformation script specified")):
        psyclone_transmute(config, input_files,
                           artefact_set=ArtefactSet.FORTRAN_COMPILER_FILES)
    output_files = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]

    assert expected == output_files


@mark.skipif(not Psyclone().is_available,
             reason="psyclone cli tool not available")
def test_psyclone_transmute_script(tmp_path, config):
    """
    Check that we catch the error if the transformation script does not have
    a .py extension (which is a PSyclone requirement).
    """

    input_files = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]

    # Expected files will be in the build output directory and
    # have the new suffix `_transmute` added.
    expected = {config.build_output / '/'.join(i.parts[1:])
                for i in input_files}
    expected = {i.with_stem(i.stem + "_transmute") for i in expected}

    script = tmp_path / "script"
    script.write_text("invalid python\n")
    with raises(RuntimeError) as err:
        psyclone_transmute(config, input_files,
                           transformation_script=lambda _a, _b: script,
                           artefact_set=ArtefactSet.FORTRAN_COMPILER_FILES)
    assert ("expected the script file \\'script\\' to have the \\'.py\\' "
            "extension" in str(err))


@mark.skipif(not Psyclone().is_available,
             reason="psyclone cli tool not available")
def test_psyclone_transmute_prebuilt(config, capsys: CaptureFixture):
    """
    Tests the handling of existing prebuild files.
    """

    input_files = \
        config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES].copy()

    # Expected files will be in the build output directory and
    # have the new suffix `_transmute` added.
    expected = {config.build_output / '/'.join(i.parts[1:])
                for i in input_files}
    expected = {i.with_stem(i.stem + "_transmute") for i in expected}

    with (warns(UserWarning,
                match="_metric_send_conn not set, cannot send metrics"),
          warns(UserWarning,
                match="No transformation script specified")):
        psyclone_transmute(config, input_files,
                           artefact_set=ArtefactSet.FORTRAN_COMPILER_FILES)

    output_files = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]
    assert expected == output_files

    captured = capsys.readouterr()
    assert "Found prebuild for" not in captured.out

    # Now rerun - remove the preprocessed filed from the previous step
    config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES] = \
        input_files.copy()

    # Now it should find prebuilds:
    with (warns(UserWarning,
                match="_metric_send_conn not set, cannot send metrics"),
          warns(UserWarning,
                match="No transformation script specified")):
        psyclone_transmute(config, input_files,
                           artefact_set=ArtefactSet.FORTRAN_COMPILER_FILES)
    output_files = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]

    assert expected == output_files
    captured = capsys.readouterr()
    assert "Found prebuild for" in captured.out


@mark.skipif(not Psyclone().is_available,
             reason="psyclone cli tool not available")
def test_psyclone_transmute_override(tmp_path, config):
    """
    Test that the override directive works.
    """

    input_files = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]

    # Expected files will be in the build output directory and
    # have the new suffix `_transmute` added.
    expected = {config.build_output / '/'.join(i.parts[1:])
                for i in input_files}
    expected = {i.with_stem(i.stem + "_transmute") for i in expected}

    overrides_folder = tmp_path / "override"
    with (warns(UserWarning,
                match="_metric_send_conn not set, cannot send metrics"),
          warns(UserWarning,
                match="No transformation script specified")):
        psyclone_transmute(
            config,
            config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES],
            artefact_set=ArtefactSet.FORTRAN_COMPILER_FILES,
            overrides_folder=overrides_folder)
    output_files = config.artefact_store[ArtefactSet.FORTRAN_COMPILER_FILES]

    assert expected == output_files
