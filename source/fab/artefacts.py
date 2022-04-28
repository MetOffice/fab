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

from fab.dep_tree import AnalysedFile
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
        return artefact_store[self.collection_name]


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
        self.targets = collections

    # todo: ensure the labelled values are iterables
    def __call__(self, artefact_store: Dict):
        super().__call__(artefact_store)
        result = []
        for target in self.targets:
            if isinstance(target, str):
                result.extend(artefact_store.get(target, []))
            elif isinstance(target, ArtefactsGetter):
                result.extend(target(artefact_store))
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
        fpaths: Iterable[Path] = artefact_store[self.collection_name]
        return suffix_filter(fpaths, self.suffixes)


class FilterBuildTree(ArtefactsGetter):
    """
    Like SuffixFilter, except the :term:`Named Collection` is expected to be a source tree dict
    of :class:`~fab.dep_tree.AnalysedFile` nodes.

    Returns a list of paths with the given suffix.

    Example::

        # The default source getter for the CompileFortran step.
        DEFAULT_SOURCE_GETTER = FilterBuildTree(suffixes=['.f90'])

    """
    def __init__(self, suffixes: Iterable[str], collection_name: str = 'build_tree'):
        """
        Args:
            - suffixes: An iterable of suffixes

        """
        self.collection_name = collection_name
        self.suffixes = suffixes

    def __call__(self, artefact_store):
        super().__call__(artefact_store)
        analysed_files: Iterable[AnalysedFile] = artefact_store[self.collection_name].values()
        return list(filter(lambda af: af.fpath.suffix in self.suffixes, analysed_files))
