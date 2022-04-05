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

from fab.util import suffix_filter


class ArtefactGetterBase(ABC):
    """
    Base class. An artefact getter will return a subset of the artefact_store.

    """
    @abstractmethod
    def __call__(self, artefact_store):
        pass


class ArtefactGetter(ArtefactGetterBase):
    """
    A simple artefact getter which returns the labelled value from the artefact_store.

    For example, `artefact_store['preprocessed_fortran']` is often a list of paths
    which can be retrieved at runtime using `ArtefactGetter('preprocessed_fortran')`.

    """
    def __init__(self, name):
        self.name = name

    def __call__(self, artefact_store):
        super().__call__(artefact_store)
        return artefact_store[self.name]


class ArtefactConcat(ArtefactGetterBase):
    """
    Returns a concatenated list of all the artefacts from the given labels.

    Assumes every label refers to an iterable.

    .. note::

        An :class:`~fab.artefacts.ArtefactGetterBase` object can be provided instead of a label.

    Example::

        # The default source code getter for the Analyse step.
        DEFAULT_SOURCE_GETTER = ArtefactConcat([
            'preprocessed_c',
            'preprocessed_fortran',
            SuffixFilter('all_source', '.f90'),
        ])

    """
    def __init__(self, targets: Iterable[Union[str, ArtefactGetterBase]]):
        """
        Args:
            - targets: An iterable containing artifact names (strings) or ArtefactGetterBase objects.

        """
        self.targets = targets

    # todo: ensure the labelled values are iterables
    def __call__(self, artefact_store: Dict):
        super().__call__(artefact_store)
        result = []
        for target in self.targets:
            if isinstance(target, str):
                result.extend(artefact_store.get(target, []))
            elif isinstance(target, ArtefactGetterBase):
                result.extend(target(artefact_store))
        return result


class SuffixFilter(ArtefactGetterBase):
    """
    An artefact getter which returns the paths in a named iterable, filtered by suffix.

    Example::

        # The default source getter for the FortranPreProcessor step.
        DEFAULT_SOURCE = SuffixFilter('all_source', '.F90')

    """
    def __init__(self, artefact_name: str, suffix: Union[str, List[str]]):
        """
        Args:
            - artifact_name: The artifact in which to find paths.
            - suffix: A suffix string including the dot, or iterable of.

        """
        self.artefact_name = artefact_name
        self.suffixes = [suffix] if isinstance(suffix, str) else suffix

    def __call__(self, artefact_store):
        super().__call__(artefact_store)
        fpaths: Iterable[Path] = artefact_store[self.artefact_name]
        return suffix_filter(fpaths, self.suffixes)


class FilterBuildTree(ArtefactGetterBase):
    """
    Like SuffixFilter, except the artifact is expected to be a source tree dict of :class:`~fab.dep_tree.AnalysedFile`s.

    Returns a list of paths with the given suffix.

    Example::

        # The default source getter for the CompileFortran step.
        DEFAULT_SOURCE_GETTER = FilterBuildTree(suffixes=['.f90'])

    """
    def __init__(self, suffixes: Iterable[str], artefact_name: str = 'build_tree'):
        """
        Args:
            - suffixes: An iterable of suffixes

        """
        self.artefact_name = artefact_name
        self.suffixes = suffixes

    def __call__(self, artefact_store):
        super().__call__(artefact_store)
        analysed_files: Iterable[Path] = artefact_store[self.artefact_name].values()
        return list(filter(lambda af: af.fpath.suffix in self.suffixes, analysed_files))
