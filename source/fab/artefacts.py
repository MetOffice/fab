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

from abc import ABC, abstractmethod
from collections import defaultdict
from enum import auto, Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

from fab.dep_tree import filter_source_tree, AnalysedDependent
from fab.util import suffix_filter


class ArtefactSet(Enum):
    '''A simple enum with the artefact types used internally in Fab.
    '''
    INITIAL_SOURCE = auto()
    PREPROCESSED_FORTRAN = auto()
    PREPROCESSED_C = auto()
    FORTRAN_BUILD_FILES = auto()
    C_BUILD_FILES = auto()
    X90_BUILD_FILES = auto()
    CURRENT_PREBUILDS = auto()
    PRAGMAD_C = auto()
    BUILD_TREES = auto()
    OBJECT_FILES = auto()
    OBJECT_ARCHIVES = auto()
    EXECUTABLES = auto()


class ArtefactStore(dict):
    '''This object stores sets of artefacts (which can be of any type).
    Each artefact is indexed by either an ArtefactSet enum, or a string.
    '''

    def __init__(self):
        '''The constructor calls reset, which will mean all the internal
        artefact categories are created.'''
        super().__init__()
        self.reset()

    def reset(self):
        '''Clears the artefact store (but does not delete any files).
        '''
        self.clear()
        for artefact in ArtefactSet:
            if artefact in [ArtefactSet.OBJECT_FILES,
                            ArtefactSet.OBJECT_ARCHIVES]:
                # ObjectFiles store a default dictionary (i.e. a non-existing
                # key will automatically add an empty `set`)
                self[artefact] = defaultdict(set)
            else:
                self[artefact] = set()

    def add(self, collection: Union[str, ArtefactSet],
            files: Union[Path, Iterable[Path]]):
        '''Adds the specified artefacts to a collection. The artefact
        can be specified as a simple string, a list of string or a set, in
        which case all individual entries of the list/set will be added.
        :param collection: the name of the collection to add this to.
        :param files: the artefacts to add.
        '''
        if isinstance(files, list):
            files = set(files)
        elif isinstance(files, Path):
            files = {files}
        elif not isinstance(files, Iterable):
            files = {Path(files)}

        self[collection].update(files)

    def update_dict(self, collection: Union[str, ArtefactSet],
                    values: Union[Path, Iterable[Path]],
                    key: Optional[str] = None):
        """
        Modifies data associated with artefact set.

        :param collection: Name or enumeration of set to modify.
        :param values: New data for set.
        :param key: Executable name associated with data. Do not specify for
                    libraries.
        """
        self[collection][key].update([values] if isinstance(values, Path)
                                     else values)

    def copy_artefacts(self, source: Union[str, ArtefactSet],
                       dest: Union[str, ArtefactSet],
                       suffixes: Optional[Union[str, List[str]]] = None):
        '''Copies all artefacts from `source` to `destination`. If a
        suffix_fiter is specified, only files with the given suffix
        will be copied.

        :param source: the source artefact set.
        :param dest: the destination artefact set.
        :param suffixes: a string or list of strings specifying the
            suffixes to copy.
        '''
        if suffixes:
            suffixes = [suffixes] if isinstance(suffixes, str) else suffixes
            self.add(dest, set(suffix_filter(self[source], suffixes)))
        else:
            self.add(dest, self[source])

    def replace(self, artefact: Union[str, ArtefactSet],
                remove_files: List[Union[str, Path]],
                add_files: Union[List[Union[str, Path]], dict]):
        '''Replaces artefacts in one artefact set with other artefacts. This
        can be used e.g to replace files that have been preprocessed
        and renamed. There is no requirement for these lists to have the
        same number of elements, nor is there any check if an artefact to
        be removed is actually in the artefact set.

        :param artefact: the artefact set to modify.
        :param remove_files: files to remove from the artefact set.
        :param add_files: files to add to the artefact set.
        '''

        art_set = self[artefact]
        if not isinstance(art_set, set):
            raise RuntimeError(f"Replacing artefacts in dictionary "
                               f"'{artefact}' is not supported.")
        art_set.difference_update(set(remove_files))
        art_set.update(add_files)


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
    A simple artefact getter which returns one :term:`Artefact Collection`
    from the artefact_store.

    Example::

        `CollectionGetter('preprocessed_fortran')`

    """
    def __init__(self, collection_name: Union[str, ArtefactSet]):
        """
        :param collection_name:
            The name of the artefact collection to retrieve.

        """
        self.collection_name = collection_name

    def __call__(self, artefact_store):
        return artefact_store.get(self.collection_name, set())


class CollectionConcat(ArtefactsGetter):
    """
    Returns a concatenated list from multiple
    :term:`Artefact Collections <Artefact Collection>` (each expected to be
    an iterable).

    An :class:`~fab.artefacts.ArtefactsGetter` can be provided instead of a
    collection_name.

    Example::

        # The default source code getter for the Analyse step might look
        # like this.
        DEFAULT_SOURCE_GETTER = CollectionConcat([
            'preprocessed_c',
            'preprocessed_fortran',
            SuffixFilter(ArtefactSet.INITIAL_SOURCE, '.f90'),
        ])

    """
    def __init__(self, collections: Iterable[Union[ArtefactSet, str,
                                                   ArtefactsGetter]]):
        """
        :param collections:
            An iterable containing collection names (strings) or
            other ArtefactsGetters.

        """
        self.collections = collections

    # todo: ensure the labelled values are iterables
    def __call__(self, artefact_store: ArtefactStore):
        # todo: this should be a set, in case a file appears in
        # multiple collections
        result = []
        for collection in self.collections:
            if isinstance(collection, (str, ArtefactSet)):
                result.extend(artefact_store.get(collection, []))
            elif isinstance(collection, ArtefactsGetter):
                result.extend(collection(artefact_store))
        return result


class SuffixFilter(ArtefactsGetter):
    """
    Returns the file paths in a :term:`Artefact Collection` (expected to be
    an iterable), filtered by suffix.

    Example::

        # The default source getter for the FortranPreProcessor step.
        DEFAULT_SOURCE = SuffixFilter(ArtefactSet.INITIAL_SOURCE, '.F90')

    """
    def __init__(self,
                 collection_name: Union[str, ArtefactSet],
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
        # todo: returning an empty list is probably "dishonest" if the
        # collection doesn't exist - return None instead?
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

        build_trees = artefact_store[ArtefactSet.BUILD_TREES]

        build_lists: Dict[str, List[AnalysedDependent]] = {}
        for root, tree in build_trees.items():
            build_lists[root] = filter_source_tree(source_tree=tree,
                                                   suffixes=self.suffixes)

        return build_lists
