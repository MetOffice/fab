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
from abc import ABC
from string import Template
from typing import List

from fab.constants import BUILD_OUTPUT, COMPILED_FILES
from fab.steps import Step, archive_objects
from fab.util import log_or_dot, run_command
from fab.artefacts import ArtefactsGetter, CollectionGetter

logger = logging.getLogger(__name__)


class DefaultLinkerSource(ArtefactsGetter):
    """
    A source getter specifically for linking.
    Looks for the default output from archiving objects, falls back to default compiler output.
    This allows a link step to work with or without a preceding object archive step.

    """
    def __call__(self, artefact_store):
        return CollectionGetter(archive_objects.DEFAULT_COLLECTION_NAME)(artefact_store) \
               or CollectionGetter(COMPILED_FILES)(artefact_store)


DEFAULT_SOURCE_GETTER = DefaultLinkerSource()


class LinkerBase(Step, ABC):
    """
    Base class for Steps which link a build target(s).

    The default artefact getter, :py:cont:`~fab.steps.link_exe.DefaultLinkerSource`, looks for any output
    from an :class:`~fab.steps.archive_objects.ArchiveObjects` step, and falls back to using output from
    compiler steps.

    :param linker: E.g 'gcc' or 'ld'.
    :param flags: A list of flags to pass to the linker.
    :param source: An :class:`~fab.artefacts.ArtefactsGetter`.
    :param name: A descriptive label for this step.

    """
    def __init__(self, linker: str, flags=None, source: ArtefactsGetter = None, name='link'):
        super().__init__(name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER
        self.linker = linker
        self.flags: List[str] = flags or []

    def call_linker(self, filename, objects):
        command = self.linker.split()
        command.extend(['-o', filename])
        command.extend(map(str, objects))
        # note: this must this come after the list of object files?
        command.extend(os.getenv('LDFLAGS', []).split())
        command.extend(self.flags)
        log_or_dot(logger, 'Link running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error linking: {err}")


class LinkExe(LinkerBase):
    """
    A build step to produce an executable for every build tree.

    """
    def run(self, artefact_store, config):
        """
        Link the object files for every build target in the artefact_store.

        """
        super().run(artefact_store, config)

        target_objects = self.source_getter(artefact_store)
        for root, objects in target_objects.items():
            self.call_linker(
                filename=str(config.project_workspace / f'{root}.exe'),
                objects=objects)


class LinkSharedObject(LinkExe):

    def __init__(self, linker: str, output_fpath: str, flags=None, source: ArtefactsGetter = None,
                 name='link shared object'):
        super().__init__(linker=linker, flags=flags, source=source, name=name)

        self.output_fpath = output_fpath

        ensure_flags = ['-fPIC', '-shared']
        for f in ensure_flags:
            if f not in self.flags:
                self.flags.append(f)

    def run(self, artefact_store, config):
        super().run(artefact_store, config)

        # We expect a single build target containing the whole codebase, with no name (as it's not a root symbol).
        target_objects = self.source_getter(artefact_store)
        assert list(target_objects.keys()) == [None]

        objects = target_objects[None]
        self.call_linker(
            filename=Template(self.output_fpath).substitute(output=config.project_workspace / BUILD_OUTPUT),
            objects=objects)
