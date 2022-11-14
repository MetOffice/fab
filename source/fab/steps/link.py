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
from typing import List, Optional

from fab.constants import OBJECT_FILES, OBJECT_ARCHIVES, EXECUTABLES
from fab.steps import Step
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
        return CollectionGetter(OBJECT_ARCHIVES)(artefact_store) \
               or CollectionGetter(OBJECT_FILES)(artefact_store)


DEFAULT_SOURCE_GETTER = DefaultLinkerSource()


class LinkerBase(Step, ABC):
    """
    Base class for Steps which link a build target(s).

    The default artefact getter, :py:const:`~fab.steps.link_exe.DefaultLinkerSource`, looks for any output
    from an :class:`~fab.steps.archive_objects.ArchiveObjects` step, and falls back to using output from
    compiler steps.

    """
    def __init__(self, linker: Optional[str] = None, flags=None, source: Optional[ArtefactsGetter] = None, name='link'):
        """
        :param linker:
            E.g 'gcc' or 'ld'.
        :param flags:
            A list of flags to pass to the linker.
        :param source:
            An optional :class:`~fab.artefacts.ArtefactsGetter`.
            Typically not required, as there is a sensible default.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(name)

        self.linker = linker or os.getenv('LD', 'ld')
        logger.info(f'linker is {self.linker}')

        self.flags: List[str] = flags or []
        self.source_getter = source or DEFAULT_SOURCE_GETTER

    def _call_linker(self, filename, objects):
        command = self.linker.split()
        command.extend(['-o', filename])
        # todo: we need to be able to specify flags which appear before the object files
        command.extend(map(str, sorted(objects)))
        # note: this must this come after the list of object files?
        command.extend(os.getenv('LDFLAGS', '').split())
        command.extend(self.flags)
        log_or_dot(logger, 'Link running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error linking:\n{err}")


class LinkExe(LinkerBase):
    """
    Link object files into an executable for every build target.

    Expects one or more build targets from its artefact getter, of the form Dict[name, object_files].

    """
    def run(self, artefact_store, config):
        super().run(artefact_store, config)

        target_objects = self.source_getter(artefact_store)
        for root, objects in target_objects.items():
            exe_path = config.project_workspace / f'{root}.exe'
            self._call_linker(filename=str(exe_path), objects=objects)
            artefact_store.setdefault(EXECUTABLES, []).append(exe_path)


# todo: the bit about Dict[None, object_files] seems too obscure - try to rethink this.
class LinkSharedObject(LinkExe):
    """
    Produce a shared object (*.so*) file from the given build target.

    Expects a *single build target* from its artefact getter, of the form Dict[None, object_files].
    We can assume the list of object files is the entire project source, compiled.

    """
    def __init__(self, output_fpath: str, linker: Optional[str] = None, flags=None,
                 source: Optional[ArtefactsGetter] = None, name='link shared object'):
        """
        Params are as for :class:`~fab.steps.link_exe.LinkerBase`, with the addition of:

        :param output_fpath:
            File path of the shared object to create.

        """
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
        self._call_linker(
            filename=Template(self.output_fpath).substitute(output=config.build_output),
            objects=objects)
