##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
This module contains :term:`Artefacts Getter` classes which return :term:`Artefact Collections <Artefact Collection>`
from the :term:`Artefact Store`.

These classes are used by the `run` method of :class:`~fab.steps.Step` classes to retrieve the artefacts
which need to be processed. Most steps have sensible defaults and can be configured with user-defined getters.

"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Union, Dict, List

from fab.constants import BUILD_TREES

from fab.dep_tree import AnalysedFile, filter_source_tree
from fab.util import suffix_filter


class ArtefactsGetter(ABC):
    """
    Abstract base class for artefact getters.

    """
    @abstractmethod
    def __call__(self, artefact_store):
        """
        :param artefact_store:
            The artefact store from which to retrieve.

        """
        pass


class CollectionGetter(ArtefactsGetter):
    """
    A simple artefact getter which returns one :term:`Artefact Collection` from the artefact_store.

    Example::

        `CollectionGetter('preprocessed_fortran')`

    """
    def __init__(self, collection_name):
        """
        :param collection_name:
            The name of the artefact collection to retrieve.

        """
        self.collection_name = collection_name

    def __call__(self, artefact_store):
        super().__call__(artefact_store)
        return artefact_store.get(self.collection_name, [])


class CollectionConcat(ArtefactsGetter):
    """
    Returns a concatenated list from multiple :term:`Artefact Collections <Artefact Collection>`
    (each expected to be an iterable).

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
        :param collections:
            An iterable containing collection names (strings) or other ArtefactsGetters.

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
    Returns the file paths in a :term:`Artefact Collection` (expected to be an iterable),
    filtered by suffix.

    Example::

        # The default source getter for the FortranPreProcessor step.
        DEFAULT_SOURCE = SuffixFilter('all_source', '.F90')

    """
    def __init__(self, collection_name: str, suffix: Union[str, List[str]]):
        """
        :param collection_name:
            The name of the artefact collection.
        :param suffix:
            A suffix string including the dot, or iterable of.

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

    Returns one list of files to compile per build tree, of the form Dict[name, List[AnalysedFile]]

    Example::

        # The default source getter for the CompileFortran step.
        DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.f90')

    """
    def __init__(self, suffix: Union[str, List[str]], collection_name: str = BUILD_TREES):
        """
        :param suffix:
            A suffix string, or iterable of, including the preceding dot.
        :param collection_name:
            The name of the artefact collection where we find the source trees.
            Defaults to the value in :py:const:`fab.constants.BUILD_TREES`.

        """
        self.collection_name = collection_name
        self.suffixes = [suffix] if isinstance(suffix, str) else suffix

    def __call__(self, artefact_store):
        super().__call__(artefact_store)

        build_trees = artefact_store[self.collection_name]

        build_lists: Dict[str, List[AnalysedFile]] = {}
        for root, tree in build_trees.items():
            build_lists[root] = filter_source_tree(source_tree=tree, suffixes=self.suffixes)

        return build_lists
