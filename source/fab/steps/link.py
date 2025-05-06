##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Link an executable.

"""
import logging
from string import Template
from typing import List, Optional

from fab.artefacts import ArtefactSet
from fab.steps import step
from fab.tools import Category
from fab.artefacts import ArtefactsGetter, CollectionGetter

logger = logging.getLogger(__name__)


class DefaultLinkerSource(ArtefactsGetter):
    """
    A source getter specifically for linking.
    Looks for the default output from archiving objects, falls back to
    default compiler output. This allows a link step to work with or without
    a preceding object archive step.

    """
    def __call__(self, artefact_store):
        return CollectionGetter(ArtefactSet.OBJECT_ARCHIVES)(artefact_store) \
               or CollectionGetter(ArtefactSet.OBJECT_FILES)(artefact_store)


@step
def link_exe(config,
             libs: Optional[List[str]] = None,
             flags: Optional[List[str]] = None,
             source: Optional[ArtefactsGetter] = None):
    """
    Link object files into an executable for every build target.

    Expects one or more build targets from its artefact getter, of the form
    Dict[name, object_files].

    The default artefact getter,
    :py:const:`~fab.steps.link_exe.DefaultLinkerSource`, looks for any output
    from an :class:`~fab.steps.archive_objects.ArchiveObjects` step, and
    falls back to using output from compiler steps.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read
        settings such as the project workspace folder or the multiprocessing
        flag.
    :param libs:
        A list of required library names to pass to the linker.
    :param flags:
        A list of additional flags to pass to the linker.
    :param source:
        An optional :class:`~fab.artefacts.ArtefactsGetter`. It defaults to the
        output from compiler steps, which typically is the expected behaviour.

    """
    linker = config.tool_box.get_tool(Category.LINKER, mpi=config.mpi,
                                      openmp=config.openmp)
    logger.info(f'Linker is {linker.name}')

    libs = libs or []
    if flags:
        linker.add_post_lib_flags(flags, config.profile)
    source_getter = source or DefaultLinkerSource()

    target_objects = source_getter(config.artefact_store)
    for root, objects in target_objects.items():
        exe_path = config.project_workspace / f'{root}'
        linker.link(objects, exe_path, config=config, libs=libs)
        config.artefact_store.add(ArtefactSet.EXECUTABLES, exe_path)


# todo: the bit about Dict[None, object_files] seems too obscure - try to
# rethink this.
@step
def link_shared_object(config, output_fpath: str, flags=None,
                       source: Optional[ArtefactsGetter] = None):
    """
    Produce a shared object (*.so*) file from the given build target.

    Expects a *single build target* from its artefact getter, of the form
    Dict[None, object_files]. We can assume the list of object files is the
    entire project source, compiled.

    Params are as for :class:`~fab.steps.link_exe.LinkerBase`, with the
    addition of:

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read
        settings such as the project workspace folder or the multiprocessing
        flag.
    :param output_fpath:
        File path of the shared object to create.
    :param flags:
        A list of flags to pass to the linker.
    :param source:
        An optional :class:`~fab.artefacts.ArtefactsGetter`.
        Typically not required, as there is a sensible default.
    """
    linker = config.tool_box[Category.LINKER]
    logger.info(f'linker is {linker}')

    flags = flags or []
    source_getter = source or DefaultLinkerSource()

    ensure_flags = ['-fPIC', '-shared']
    for f in ensure_flags:
        if f not in flags:
            flags.append(f)

    # We expect a single build target containing the whole codebase, with no
    # name (as it's not a root symbol).
    target_objects = source_getter(config.artefact_store)
    assert list(target_objects.keys()) == [None]

    objects = target_objects[None]
    out_name = Template(output_fpath).substitute(output=config.build_output)
    linker.add_post_lib_flags(flags, config.profile)
    linker.link(objects, out_name, config=config)
