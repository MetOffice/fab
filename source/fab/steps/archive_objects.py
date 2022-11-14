##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Object archive creation from a list of object files for use in static linking.

"""

import logging
from string import Template
from typing import Dict, Optional

from fab.constants import OBJECT_FILES, OBJECT_ARCHIVES
from fab.steps import Step
from fab.util import log_or_dot, run_command
from fab.artefacts import ArtefactsGetter, CollectionGetter

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = CollectionGetter(OBJECT_FILES)


# todo: two diagrams showing the flow of artefacts in the exe and library use cases
#       show how the library has a single build target with None as the name.

# todo: all this documentation for such a simple step - should we split it up somehow?

class ArchiveObjects(Step):
    """
    Create an object archive for every build target, from their object files.

    An object archive is a set of object (*.o*) files bundled into a single file, typically with a *.a* extension.

    Expects one or more build targets from its artefact getter, of the form Dict[name, object_files].
    By default, it finds the build targets and their object files in the artefact collection named by
    :py:const:`fab.constants.COMPILED_FILES`.

    This step has three use cases:

    * The **object archive** is the end goal of the build.
    * The object archive is a convenience step before linking a **shared object**.
    * One or more object archives as convenience steps before linking **executables**.

    The benefit of creating an object archive before linking is simply to reduce the size
    of the linker command, which might otherwise include thousands of .o files, making any error output
    difficult to read. You don't have to use this step before linking.
    The linker step has a default artefact getter which will work with or without this preceding step.

    **Creating a Static or Shared Library:**

    When building a library there is expected to be a single build target with a `None` name.
    This typically happens when configuring the :class:`~fab.steps.analyser.Analyser` step *without* a root symbol.
    We can assume the list of object files is the entire project source, compiled.

    In this case you must specify an *output_fpath*.

    **Creating Executables:**

    When creating executables, there is expected to be one or more build targets, each with a name.
    This typically happens when configuring the :class:`~fab.steps.analyser.Analyser` step *with* a root symbol(s).
    We can assume each list of object files is sufficient to build each *<root_symbol>.exe*.

    In this case you cannot specify an *output_fpath* path because they are automatically created from the
    target name.

    """
    # todo: the output path should not be an abs fpath, it should be relative to the proj folder
    def __init__(self, source: Optional[ArtefactsGetter] = None, archiver='ar',
                 output_fpath=None, output_collection=OBJECT_ARCHIVES, name='archive objects'):
        """
        :param source:
            An :class:`~fab.artefacts.ArtefactsGetter` which give us our lists of objects to archive.
            The artefacts are expected to be of the form `Dict[root_symbol_name, list_of_object_files]`.
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
        self.output_fpath = str(output_fpath) if output_fpath else None
        self.output_collection = output_collection

    def run(self, artefact_store: Dict, config):
        """
        :param artefact_store:
            Contains artefacts created by previous Steps, and where we add our new artefacts.
            This is where the given :class:`~fab.artefacts.ArtefactsGetter` finds the artefacts to process.
        :param config:
            The :class:`fab.build_config.BuildConfig` object where we can read settings
            such as the project workspace folder or the multiprocessing flag.

        """
        super().run(artefact_store, config)

        target_objects = self.source_getter(artefact_store)
        assert target_objects.keys()
        if self.output_fpath and list(target_objects.keys()) != [None]:
            raise ValueError("You must not specify an output path (library) when there are root symbols (exes)")
        if not self.output_fpath and list(target_objects.keys()) == [None]:
            raise ValueError("You must specify an output path when building a library.")

        output_archives = artefact_store.setdefault(self.output_collection, {})
        for root, objects in target_objects.items():

            if root:
                # we're building an object archive for an exe
                output_fpath = str(config.build_output / f'{root}.a')
            else:
                # we're building a single object archive with a given filename
                assert len(target_objects) == 1, "unexpected root of None with multiple build targets"
                output_fpath = Template(str(self.output_fpath)).substitute(
                    output=config.build_output)

            command = [self.archiver]
            command.extend(['cr', output_fpath])
            command.extend(map(str, sorted(objects)))

            log_or_dot(logger, 'CreateObjectArchive running command: ' + ' '.join(command))
            try:
                run_command(command)
            except Exception as err:
                raise Exception(f"error creating object archive:\n{err}")

            output_archives[root] = [output_fpath]
