##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
This module contains "artefact getter" classes which return a subset of the artefact_store.

Their intended use is in :class:`~fab.steps.Step` classes, which can be preconfigured to use sensible defaults,
or receive user-defined getters.

"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Union, Dict, List

from fab.constants import BUILD_TREES

from fab.dep_tree import AnalysedFile, filter_source_tree
from fab.util import suffix_filter


class ArtefactsGetter(ABC):
    """
    Abstract base class for artefacts getters, which return a subset of the artefact_store.

    """
    @abstractmethod
    def __call__(self, artefact_store):
        pass


class CollectionGetter(ArtefactsGetter):
    """
    A simple artefacts getter which returns a :term:`Named Collection` from the artefact_store.

    For example, ``artefact_store['preprocessed_fortran']`` is often a list of paths
    which can be retrieved at runtime using ``CollectionGetter('preprocessed_fortran')``.

    """
    def __init__(self, collection_name):
        self.collection_name = collection_name

    def __call__(self, artefact_store):
        super().__call__(artefact_store)
        return artefact_store.get(self.collection_name, [])


class CollectionConcat(ArtefactsGetter):
    """
    Returns a concatenated list of :term:`Named Collections <Named Collection>` (each expected to be an iterable).

    .. note::

        An :class:`~fab.artefacts.ArtefactsGetter` can be provided instead of a collection_name.

    Example::

        # The default source code getter for the Analyse step might look like this.
        DEFAULT_SOURCE_GETTER = CollectionConcat([
            'preprocessed_c',
            'preprocessed_fortran',
            SuffixFilter('all_source', '.f90'),
        ])

    """
    def __init__(self, collections: Iterable[Union[str, ArtefactsGetter]]):
        """
        Args:
            - collections: An iterable containing collection names (strings) or other ArtefactsGetters.

        """
        self.collections = collections

    # todo: ensure the labelled values are iterables
    def __call__(self, artefact_store: Dict):
        super().__call__(artefact_store)
        result = []
        for collection in self.collections:
            if isinstance(collection, str):
                result.extend(artefact_store.get(collection, []))
            elif isinstance(collection, ArtefactsGetter):
                result.extend(collection(artefact_store))
        return result


class SuffixFilter(ArtefactsGetter):
    """
    An artefacts getter which returns the paths in a :term:`Named Collection` (expected to be an iterable),
    filtered by suffix.

    Example::

        # The default source getter for the FortranPreProcessor step.
        DEFAULT_SOURCE = SuffixFilter('all_source', '.F90')

    """
    def __init__(self, collection_name: str, suffix: Union[str, List[str]]):
        """
        Args:
            - collection_name: The :term:`Named Collection` in which to find paths.
            - suffix: A suffix string including the dot, or iterable of.

        """
        self.collection_name = collection_name
        self.suffixes = [suffix] if isinstance(suffix, str) else suffix

    def __call__(self, artefact_store):
        super().__call__(artefact_store)
        # todo: returning an empty list is probably "dishonest" if the collection doesn't exist - return None instead?
        fpaths: Iterable[Path] = artefact_store.get(self.collection_name, [])
        return suffix_filter(fpaths, self.suffixes)


class FilterBuildTrees(ArtefactsGetter):
    """
    Filter build trees by suffix.

    Returns a list of paths for each build tree.

    """
    def __init__(self, suffix: Union[str, List[str]], collection_name: str = BUILD_TREES):
        """
        The given *collection_name* specifies which artefact collection contains the build trees.
        If no name is provided, it defaults to the value in :py:const:`fab.constants.BUILD_TREES`,
        as used by the analyse step.

        :param suffix:
            A string, or iterable of, including the preceding dot.
        :param collection_name:
            The name of the artefact collection where we find the source trees to build.
            Defaults to the value in :py:const:`fab.constants.BUILD_TREES`.

        Example::

            # The default source getter for the CompileFortran step.
            DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.f90')

        """
        self.collection_name = collection_name
        self.suffixes = [suffix] if isinstance(suffix, str) else suffix

    def __call__(self, artefact_store):
        """Get a list of files to compile for each target source tree."""
        super().__call__(artefact_store)

        build_trees = artefact_store[self.collection_name]

        build_lists: Dict[str, List[AnalysedFile]] = {}
        for root, tree in build_trees.items():
            build_lists[root] = filter_source_tree(source_tree=tree, suffixes=self.suffixes)

        return build_lists
