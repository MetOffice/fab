##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
This module contains :term:`Artefacts Getter` classes which return
:term:`Artefact Collections <Artefact Collection>` from the
:term:`Artefact Store`.

These classes are used by the `run` method of :class:`~fab.steps.Step`
classes to retrieve the artefacts which need to be processed. Most steps
have sensible defaults and can be configured with user-defined getters.

"""
# We can use ArtefactStore as type annotation (esp. ArtefactStore.Artefact)
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import auto, Enum
from pathlib import Path
from typing import Iterable, Union, Dict, List, Set

from fab.dep_tree import filter_source_tree, AnalysedDependent
from fab.util import suffix_filter


class ArtefactStore(dict):
    '''This object stores artefacts (which can be of any type). Each artefact
    is indexed by a string.
    '''

    class Artefacts(Enum):
        '''A simple enum with the artefact types used internally in Fab.
        '''
        PREPROCESSED_FORTRAN = auto()
        PREPROCESSED_C = auto()
        FORTRAN_BUILD_FILES = auto()
        C_BUILD_FILES = auto()
        X90_BUILD_FILES = auto()
        CURRENT_PREBUILDS = auto()
        BUILD_TREES = auto()

    def __init__(self):
        '''The constructor calls reset, which will mean all the internal
        artefact categories are created.'''
        super().__init__()
        self.reset()

    def reset(self):
        '''Clears the artefact store (but does not delete any files).
        '''
        self.clear()
        for artefact in self.Artefacts:
            self[artefact] = set()

    def _add_files_to_artefact(self, collection: Union[str, ArtefactStore.Artefacts],
                               files: Union[str, List[str], Set[str]]):
        if isinstance(files, list):
            files = set(files)
        elif not isinstance(files, set):
            # We need to use a list, otherwise each character is added
            files = set([files])

        self[collection].update(files)

    def add_fortran_build_files(self, files: Union[str, List[str], Set[str]]):
        self._add_files_to_artefact(self.Artefacts.FORTRAN_BUILD_FILES, files)

    def get_fortran_build_files(self):
        return self[self.Artefacts.FORTRAN_BUILD_FILES]

    def add_c_build_files(self, files: Union[str, List[str], Set[str]]):
        self._add_files_to_artefact(self.Artefacts.C_BUILD_FILES, files)

    def add_x90_build_files(self, files: Union[str, List[str], Set[str]]):
        self._add_files_to_artefact(self.Artefacts.X90_BUILD_FILES, files)


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
        raise NotImplementedError(f"__call__ must be implemented for "
                                  f"'{type(self).__name__}'.")


class CollectionGetter(ArtefactsGetter):
    """
    A simple artefact getter which returns one :term:`Artefact Collection` from the artefact_store.

    Example::

        `CollectionGetter('preprocessed_fortran')`

    """
    def __init__(self, collection_name: Union[str, ArtefactStore.Artefacts]):
        """
        :param collection_name:
            The name of the artefact collection to retrieve.

        """
        self.collection_name = collection_name

    def __call__(self, artefact_store):
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
    def __init__(self, collections: Iterable[Union[ArtefactStore.Artefacts, str,
                                                   ArtefactsGetter]]):
        """
        :param collections:
            An iterable containing collection names (strings) or other ArtefactsGetters.

        """
        self.collections = collections

    # todo: ensure the labelled values are iterables
    def __call__(self, artefact_store: ArtefactStore):
        # todo: this should be a set, in case a file appears in multiple collections
        result = []
        for collection in self.collections:
            if isinstance(collection, (str, ArtefactStore.Artefacts)):
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
    def __init__(self,
                 collection_name: Union[str, ArtefactStore.Artefacts],
                 suffix: Union[str, List[str]]):
        """
        :param collection_name:
            The name of the artefact collection.
        :param suffix:
            A suffix string including the dot, or iterable of.

        """
        self.collection_name = collection_name
        self.suffixes = [suffix] if isinstance(suffix, str) else suffix

    def __call__(self, artefact_store: ArtefactStore):
        # todo: returning an empty list is probably "dishonest" if the collection doesn't exist - return None instead?
        fpaths: Iterable[Path] = artefact_store.get(self.collection_name, [])
        return suffix_filter(fpaths, self.suffixes)


class FilterBuildTrees(ArtefactsGetter):
    """
    Filter build trees by suffix.

    Example::

        # The default source getter for the CompileFortran step.
        DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.f90')

    :returns: one list of files to compile per build tree, of the form
        Dict[name, List[AnalysedDependent]]

    """
    def __init__(self, suffix: Union[str, List[str]]):
        """
        :param suffix:
            A suffix string, or iterable of, including the preceding dot.

        """
        self.suffixes = [suffix] if isinstance(suffix, str) else suffix

    def __call__(self, artefact_store: ArtefactStore):

        build_trees = artefact_store[ArtefactStore.Artefacts.BUILD_TREES]

        build_lists: Dict[str, List[AnalysedDependent]] = {}
        for root, tree in build_trees.items():
            build_lists[root] = filter_source_tree(source_tree=tree, suffixes=self.suffixes)

        return build_lists
