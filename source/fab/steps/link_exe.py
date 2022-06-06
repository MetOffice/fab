##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Link an executable.

"""
import logging
import os
from string import Template
from typing import List

from fab import artefacts
from fab.constants import BUILD_OUTPUT
from fab.steps import Step, archive_objects
from fab.util import log_or_dot, run_command
from fab.artefacts import ArtefactsGetter, CollectionGetter

logger = logging.getLogger(__name__)


# class DefaultLinkerSource(ArtefactsGetter):
#     """
#     A source getter specifically for linking.
#     Looks for the default output from ArchiveObjects, falls back to artefacts.CompiledFortranAndC.
#     This allows a link step to work with or without a preceding object archive step.
#
#     """
#     def __call__(self, artefact_store):
#         return CollectionGetter(archive_objects.DEFAULT_COLLECTION_NAME)(artefact_store) \
#                or artefacts.CompiledFortranAndC(artefact_store)
#
# DEFAULT_SOURCE_GETTER = DefaultLinkerSource()

DEFAULT_SOURCE_GETTER = CollectionGetter('build_trees')


class LinkExe(Step):
    """
    A build step to produce an executable for every build tree in a given artefact collection.

    Defaults to using the XXX collection

    :param linker: E.g 'gcc' or 'ld'.
    :param flags: A list of flags to pass to the linker.
    :param source: An :class:`~fab.artefacts.ArtefactsGetter`.
    :param name: A descriptive label for his step, defaulting to 'link exe'.

    """
    def __init__(self, linker: str, flags=None, source: ArtefactsGetter = None, name='link exe'):
        # output_fpath='$output/../jules.exe'

        super().__init__(name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER
        self.linker = linker
        self.flags: List[str] = flags or []

    def run(self, artefact_store, config):
        """
        Links all the object files in the artefact_store.

        By default, it finds the object files under the labels *compiled_c* and *compiled_fortran*.

        """
        super().run(artefact_store, config)

        build_trees = self.source_getter(artefact_store)
        for build_tree in build_trees:
            self.link_build_tree(build_tree, config)

    def link_build_tree(self, build_tree, config):
        # compiled_files = self.source_getter(artefact_store)

        root_sy

        command = self.linker.split()
        command.extend(['-o', Template(self.output_fpath).substitute(
            output=str(config.project_workspace / BUILD_OUTPUT))])
        command.extend(map(str, compiled_files))
        # note: this must this come after the list of object files?
        command.extend(os.getenv('LDFLAGS', []).split())
        command.extend(self.flags)
        log_or_dot(logger, 'Link running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error linking: {err}")


class LinkSharedObject(LinkExe):

    def __init__(self, linker: str, output_fpath: str, flags=None, source: ArtefactsGetter = None,
                 name='link shared object'):
        super().__init__(linker=linker, flags=flags, output_fpath=output_fpath, source=source, name=name)

        ensure_flags = ['-fPIC', '-shared']
        for f in ensure_flags:
            if f not in self.flags:
                self.flags.append(f)
