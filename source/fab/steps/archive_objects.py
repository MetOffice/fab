##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Object archive (.a) creation from a list of object files (.o) for use in static linking.

"""

import logging
from string import Template
from typing import Dict

from fab.constants import BUILD_OUTPUT, COMPILED_FILES, OBJECT_ARCHIVES
from fab.steps import Step
from fab.util import log_or_dot, run_command
from fab.artefacts import ArtefactsGetter, CollectionGetter

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = CollectionGetter(COMPILED_FILES)
DEFAULT_COLLECTION_NAME = OBJECT_ARCHIVES


# todo: two diagrams showing the flow of artefacts in the exe and library use cases
#       show how the library has a single build target with None as the name.


class ArchiveObjects(Step):
    """
    Creates an object archive file from the named artefact collection,
    defaulting to :py:const:`~fab.constants.TARGET_OBJECT_FILES`, as created by compiler steps.

    Expects one or more build targets in the artefact collection, of the form Dict[name, object_files].

    When building exes, each build target consists of a name and a list of compiled files.
    Each name is a root symbol, as given to the :class:`@fab.steps.analyse.Analyse` step.
    The target names and compiled files are output from the compiler steps.
    This step will produce an archive object for each exe, to be used by the subsequent linker step.

    When building a shared object there is expected to be a single build target with no name,
    and the object files are created from the entire project source.

    .. note::

        When creating a static library, you must specify the *output_fpath*.
        This can use templating where "$output" is replaced with the output folder.

        When creating executables, this step can be useful before linking as it reduces the length of the
        linker command (by replacing the list of object files with a single archive file).
        In this case, you cannot provide an *output_fpath*.

    :param archiver: The archiver executable. Defaults to 'ar'.
    :param output_fpath: The file path of the output archive file.

    """

    def __init__(self, source: ArtefactsGetter = None, archiver='ar',
                 output_fpath=None, output_collection=DEFAULT_COLLECTION_NAME, name='archive objects'):
        super().__init__(name)

        self.source_getter = source or DEFAULT_SOURCE_GETTER
        self.archiver = archiver
        self.output_fpath = output_fpath
        self.output_collection = output_collection

    def run(self, artefact_store: Dict, config):
        """
        Creates an object archive from the all the object files in the artefact store.

        By default, it finds the object files under the labels *compiled_c* and *compiled_fortran*.

        """
        super().run(artefact_store, config)

        # We're expecting one or more build targets in the artefact store.
        # When building exes, each build target has a name and a list of compiled files.
        # When building a shared object there is a single build target with no name.
        target_objects = self.source_getter(artefact_store)
        assert target_objects.keys()
        if self.output_fpath and list(target_objects.keys()) != [None]:
            raise ValueError("You must not specify an output path (library) when there are root symbols (exes)")
        if not self.output_fpath and list(target_objects.keys()) == [None]:
            raise ValueError("You must specify an output path when building a library.")

        target_archives = artefact_store.setdefault(self.output_collection, {})
        for root, objects in target_objects.items():

            if root:
                # we're building an object archive for an exe
                output_fpath = str(config.project_workspace / BUILD_OUTPUT / f'{root}.a')
            else:
                # we're building a single object archive with a given filename
                assert len(target_objects) == 1, "unexpected root of None with multiple targets"
                output_fpath = Template(self.output_fpath).substitute(output=config.project_workspace / BUILD_OUTPUT)

            command = [self.archiver]
            command.extend(['cr', output_fpath])
            command.extend(map(str, sorted(objects)))

            log_or_dot(logger, 'CreateObjectArchive running command: ' + ' '.join(command))
            try:
                run_command(command)
            except Exception as err:
                raise Exception(f"error creating object archive: {err}")

            target_archives[root] = [output_fpath]
