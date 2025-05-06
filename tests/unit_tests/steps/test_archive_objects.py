##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Test for the archive step.
"""
from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem
from pytest import raises, warns
from pytest_subprocess.fake_process import FakeProcess

from tests.conftest import call_list

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps.archive_objects import archive_objects
from fab.tools.category import Category


class TestArchiveObjects:
    """
    Test the achive step.
    """
    def test_for_exes(self, stub_tool_box,
                      fake_process: FakeProcess,
                      fs: FakeFilesystem) -> None:
        """
        As used when archiving before linking exes.
        """
        version_command = ['ar', '--version']
        fake_process.register(version_command, stdout='1.2.3')
        commands = []
        commands.append(version_command)
        targets = ['prog1', 'prog2']
        for target in targets:
            ar_command = ['ar', 'cr', f'/fab/proj/build_output/{target}.a',
                          f'{target}.o', 'util.o']
            fake_process.register(ar_command)
            commands.append(ar_command)

        config = BuildConfig('proj', stub_tool_box, fab_workspace=Path('/fab'))
        for target in targets:
            config.artefact_store.update_dict(
                ArtefactSet.OBJECT_FILES,
                {f'{target}.o', 'util.o'},
                target
            )

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            archive_objects(config=config)
        assert call_list(fake_process) == commands

        # ensure the correct artefacts were created
        assert config.artefact_store[ArtefactSet.OBJECT_ARCHIVES] == {
            target: {str(config.build_output / f'{target}.a')}
            for target in targets}

    def test_for_library(self, stub_tool_box,
                         fake_process: FakeProcess,
                         fs: FakeFilesystem) -> None:
        """
        As used when building an object archive or archiving before linking
        a shared library.
        """
        help_command = ['ar', '--version']
        fake_process.register(help_command, stdout='1.0.0')
        ar_command = ['ar', 'cr', '/fab/proj/build_output/mylib.a',
                      'util1.o', 'util2.o']
        fake_process.register(ar_command)

        config = BuildConfig('proj', stub_tool_box, fab_workspace=Path('/fab'),
                             multiprocessing=False)
        config.artefact_store.update_dict(
            ArtefactSet.OBJECT_FILES, {'util1.o', 'util2.o'}, None
        )

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            archive_objects(config=config,
                            output_fpath=config.build_output / 'mylib.a')
        assert call_list(fake_process) == [ar_command]

        # ensure the correct artefacts were created
        assert config.artefact_store[ArtefactSet.OBJECT_ARCHIVES] == {
            None: {str(config.build_output / 'mylib.a')}}

    def test_incorrect_tool(self, stub_tool_box):
        """
        Test that an incorrect archive tool is detected.
        """
        config = BuildConfig('proj', stub_tool_box)
        cc = stub_tool_box.get_tool(Category.C_COMPILER, config.mpi, config.openmp)
        # And set its category to be AR
        cc._category = Category.AR
        # Now add this 'ar' tool to the tool box
        stub_tool_box.add_tool(cc)

        with raises(RuntimeError) as err:
            archive_objects(config=config,
                            output_fpath=config.build_output / 'mylib.a')
        assert str(err.value) == ("Unexpected tool 'some C compiler' of type "
                                  "'<class 'fab.tools.compiler.CCompiler'>' "
                                  "instead of Ar")
