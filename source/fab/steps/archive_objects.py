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


# todo: two diagrams showing the flow of artefacts in the exe and library use cases
#       show how the library has a single build target with None as the name.


class ArchiveObjects(Step):
    """
    Create an object archive for every build target.

    Expects one or more build targets from its artefact getter, of the form Dict[name, object_files].

    An object archive is just some object (*.o*) files bundled into a single file, typically with a *.a* extension.

    This step has two use cases:

    * Building a library for static linking, typically as the end product of a build config.
      This requires the user to provide a file name to create.
    * Building one or more object archives for use by a subsequent linker step.
      This automatically generates the output file names.


    **Creating a Static Library:**

    When building a shared object there is expected to be a single build target with a name of `None`.
    This typically happens when configuring the :class:`~fab.steps.analyser.Analyser` step *without* a root symbol.
    We can assume the list of object files is the entire project source, compiled.

    In this case you must specify an output file path.

    **Creating Linker Input:**

    When creating linker input, there is expected to be one or more build targets, each with a name.
    This typically happens when configuring the :class:`~fab.steps.analyser.Analyser` step *with* a root symbol(s).
    We can assume each list of object files is sufficient to build each *<root_symbol>.exe*.

    In this case you cannot specify an output file path because they are automatically created from the
    target name.

    The benefit of this use case is simply to reduce the size of the subsequent linker command, which might
    otherwise include thousands of .o files, making any error output difficult to read.
    You don't have to use this step when making exes. The linker step has a default artefact getter which will
    work with or without this step.

    """
    def __init__(self, source: ArtefactsGetter = None, archiver='ar',
                 output_fpath=None, output_collection=OBJECT_ARCHIVES, name='archive objects'):
        """
        :param archiver:
            The archiver executable. Defaults to 'ar'.
        :param output_fpath:
            The file path of the archive file to create.
            This string can include templating, where "$output" is replaced with the output folder.

            * Must be specified when building a library file (no build target name).
            * Must not be specified when building linker input (one or more build target names).
        :param output_collection:
            The name of the artefact collection to create. Defaults to the name in
            :const:`fab.constants.OBJECT_ARCHIVES`.

        """
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
                assert len(target_objects) == 1, "unexpected root of None with multiple build targets"
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
