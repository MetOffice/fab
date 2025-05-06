##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Exercises
"""
from os import walk as os_walk
from pathlib import Path
from typing import List

from pytest import raises, warns

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps.root_inc_files import root_inc_files
from fab.tools.tool_box import ToolBox


class TestRootIncFiles:
    """
    Tests include files are handled correctly.
    """
    def test_vanilla(self, tmp_path: Path) -> None:
        """
        Tests include files is coped to work directory.
        """
        source_dir = tmp_path / 'source'
        source_dir.mkdir()
        inc_files = [source_dir / 'bar.inc']
        inc_files[0].write_text("Some include file.")

        config = BuildConfig('proj', ToolBox())
        config.artefact_store[ArtefactSet.INITIAL_SOURCE] = inc_files

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"), \
             warns(DeprecationWarning,
                   match="RootIncFiles is deprecated as .inc files are due to be removed."):
            root_inc_files(config)
        assert (config.build_output / inc_files[0]).read_text() \
            == "Some include file."

    def test_skip_output_folder(self, stub_tool_box: ToolBox, fs) -> None:
        """
        Tests files already in output directory not copied.
        """
        Path('/foo/source').mkdir(parents=True)
        Path('/foo/source/bar.inc').write_text("An include file.")

        config = BuildConfig('proj', stub_tool_box, fab_workspace=Path('/fab'))
        inc_files = [Path('/foo/source/bar.inc'),
                     config.build_output / 'fab.inc']
        config.artefact_store[ArtefactSet.INITIAL_SOURCE] = inc_files

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"), \
             warns(DeprecationWarning,
                   match="RootIncFiles is deprecated as .inc files are due to be removed."):
            root_inc_files(config)
        #
        # It's not clear why there is an unexepcted temporary directory which
        # needs to be ignored.
        #
        # ToDo: Find out where /tmp is coming from and stop it.
        #
        filetree: List[Path] = []
        for path, _, files in os_walk('/'):
            for file in files:
                if file == 'tmp':
                    continue
                filetree.append(Path(path) / file)
        assert sorted(filetree) == [Path('/fab/proj/build_output/bar.inc'),
                                    Path('/foo/source/bar.inc')]

    def test_name_clash(self, stub_tool_box: ToolBox, fs) -> None:
        """
        Tests duplicate file leaf names.
        """
        Path('/foo/source').mkdir(parents=True)
        Path('/foo/source/bar.inc').write_text("The source of the Nile.")
        Path('/foo/sauce').mkdir(parents=True)
        Path('/foo/sauce/bar.inc').write_text("Nile sauce.")
        inc_files = [Path('/foo/source/bar.inc'), Path('/foo/sauce/bar.inc')]

        config = BuildConfig('proj', stub_tool_box)
        config.artefact_store[ArtefactSet.INITIAL_SOURCE] = inc_files

        with raises(FileExistsError), \
            warns(DeprecationWarning,
                  match="RootIncFiles is deprecated as .inc "
                        "files are due to be removed."):
            root_inc_files(config)
