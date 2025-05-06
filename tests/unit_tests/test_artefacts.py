'''Tests the artefacts file.
'''

from unittest import mock
from unittest.mock import call
from pathlib import Path
import pytest

from fab.artefacts import (ArtefactSet, ArtefactStore, ArtefactsGetter,
                           CollectionConcat, CollectionGetter,
                           FilterBuildTrees, SuffixFilter)


def test_artefact_store() -> None:
    '''Tests the ArtefactStore class.'''
    artefact_store = ArtefactStore()
    assert len(artefact_store) == len(ArtefactSet)
    assert isinstance(artefact_store, dict)
    for artefact in ArtefactSet:
        if artefact in [ArtefactSet.OBJECT_FILES,
                        ArtefactSet.OBJECT_ARCHIVES]:
            assert isinstance(artefact_store[artefact], dict)
        else:
            assert isinstance(artefact_store[artefact], set)


def test_artefact_store_copy() -> None:
    '''Tests the add and copy operations.'''
    artefact_store = ArtefactStore()
    # We need paths for suffix filtering, so create some
    a = Path("a.f90")
    b = Path("b.F90")
    c = Path("c.f90")
    d = Path("d.F90.nocopy")
    e = Path("e.f90.donotcopyeither")
    # Try adding a single path, a set and a list:
    artefact_store.add(ArtefactSet.INITIAL_SOURCE, a)
    artefact_store.copy_artefacts(ArtefactSet.INITIAL_SOURCE,
                                  ArtefactSet.CURRENT_PREBUILDS)
    assert artefact_store[ArtefactSet.CURRENT_PREBUILDS] == set([a])
    artefact_store.add(ArtefactSet.INITIAL_SOURCE, [b, c])
    artefact_store.add(ArtefactSet.INITIAL_SOURCE, set([d, e]))
    assert (artefact_store[ArtefactSet.INITIAL_SOURCE] ==
            set([a, b, c, d, e]))

    # Make sure that the previous copy did not get modified:
    assert artefact_store[ArtefactSet.CURRENT_PREBUILDS] == set([a])
    artefact_store.copy_artefacts(ArtefactSet.INITIAL_SOURCE,
                                  ArtefactSet.CURRENT_PREBUILDS)
    assert (artefact_store[ArtefactSet.CURRENT_PREBUILDS] ==
            set([a, b, c, d, e]))
    # Now copy with suffix filtering:
    artefact_store.copy_artefacts(ArtefactSet.INITIAL_SOURCE,
                                  ArtefactSet.FORTRAN_BUILD_FILES,
                                  suffixes=[".F90", ".f90"])
    assert artefact_store[ArtefactSet.FORTRAN_BUILD_FILES] == set([a, b, c])

    # Make sure filtering is case sensitive
    artefact_store.copy_artefacts(ArtefactSet.INITIAL_SOURCE,
                                  ArtefactSet.C_BUILD_FILES,
                                  suffixes=[".f90"])
    assert artefact_store[ArtefactSet.C_BUILD_FILES] == set([a, c])


def test_artefact_store_update_dict() -> None:
    '''Tests the update_dict function.'''
    artefact_store = ArtefactStore()
    artefact_store.update_dict(ArtefactSet.OBJECT_FILES, [Path("AA")], "a")
    assert artefact_store[ArtefactSet.OBJECT_FILES] == {"a": {Path("AA")}}
    artefact_store.update_dict(ArtefactSet.OBJECT_FILES, set([Path("BB")]), "b")
    assert (artefact_store[ArtefactSet.OBJECT_FILES] == {"a": {Path("AA")},
                                                         "b": {Path("BB")}})


def test_artefact_store_replace() -> None:
    '''Tests the replace function.'''
    artefact_store = ArtefactStore()
    artefact_store.add(ArtefactSet.INITIAL_SOURCE, [Path("a"), Path("b"),
                                                    Path("c")])
    artefact_store.replace(ArtefactSet.INITIAL_SOURCE,
                           remove_files=[Path("a"), Path("b")],
                           add_files=[Path("B")])
    assert artefact_store[ArtefactSet.INITIAL_SOURCE] == set([Path("B"),
                                                              Path("c")])

    # Test the behaviour for dictionaries
    with pytest.raises(RuntimeError) as err:
        artefact_store.replace(ArtefactSet.OBJECT_FILES,
                               remove_files=[Path("a")], add_files=["c"])
    assert ("Replacing artefacts in dictionary 'ArtefactSet.OBJECT_FILES' "
            "is not supported" in str(err.value))


def test_artefacts_getter():
    '''Test that ArtefactsGetter is a proper AbstractClass
    and that a NotImplemented error is raised if a derived
    class is trying to call the base class.
    '''

    # First check that we can't instantiate
    # a class that doesn't implement __call__:
    # ----------------------------------------
    class MyClass(ArtefactsGetter):
        pass

    with pytest.raises(TypeError) as err:
        _ = MyClass()
    # The actual error messages changes slightly from python
    # version to version:
    # 3.7: ... with abstract methods
    # 3.8: ... with abstract method
    # 3.12: ... without an implementation for abstract
    # so we only test for the begin which is identical:
    assert "Can't instantiate abstract class MyClass with" in str(err.value)

    # Now test that we can raise the NotImplementedError
    # --------------------------------------------------
    class MyClassWithCall(ArtefactsGetter):
        def __call__(self, artefact_store):
            super().__call__(artefact_store)

    my_class_with_call = MyClassWithCall()
    with pytest.raises(NotImplementedError) as err:
        my_class_with_call("not-used")
    assert ("__call__ must be implemented for 'MyClassWithCall'"
            in str(err.value))


class TestFilterBuildTrees():
    '''Tests for FilterBuildTrees.'''

    @pytest.fixture
    def artefact_store(self) -> ArtefactStore:
        '''A fixture that returns an ArtefactStore with
        some elements.'''
        artefact_store = ArtefactStore()
        build_trees = ArtefactSet.BUILD_TREES
        artefact_store[build_trees] = {'tree1': {'a.foo': None,
                                                 'b.foo': None,
                                                 'c.bar': None, },
                                       'tree2': {'d.foo': None,
                                                 'e.foo': None,
                                                 'f.bar': None, },
                                       }
        return artefact_store

    def test_single_suffix(self, artefact_store) -> None:
        '''Ensure the artefact getter passes through the trees properly to
        the filter func.'''

        # run the artefact getter
        filter_build_trees = FilterBuildTrees('.foo')
        with mock.patch('fab.artefacts.filter_source_tree') as mock_filter:
            filter_build_trees(artefact_store)

        build_trees = ArtefactSet.BUILD_TREES
        mock_filter.assert_has_calls([
            call(source_tree=artefact_store[build_trees]['tree1'],
                 suffixes=['.foo']),
            call(source_tree=artefact_store[build_trees]['tree2'],
                 suffixes=['.foo']),
        ])

    def test_multiple_suffixes(self, artefact_store) -> None:
        '''Test it works with multiple suffixes provided.'''
        filter_build_trees = FilterBuildTrees(['.foo', '.bar'])
        with mock.patch('fab.artefacts.filter_source_tree') as mock_filter:
            filter_build_trees(artefact_store)

        build_trees = ArtefactSet.BUILD_TREES
        mock_filter.assert_has_calls([
            call(source_tree=artefact_store[build_trees]['tree1'],
                 suffixes=['.foo', '.bar']),
            call(source_tree=artefact_store[build_trees]['tree2'],
                 suffixes=['.foo', '.bar']),
        ])


def test_collection_getter() -> None:
    '''Test CollectionGetter.'''
    artefact_store = ArtefactStore()
    artefact_store.add(ArtefactSet.INITIAL_SOURCE, ["a", "b", "c"])
    cg = CollectionGetter(ArtefactSet.INITIAL_SOURCE)
    assert artefact_store[ArtefactSet.INITIAL_SOURCE] == cg(artefact_store)


def test_collection_concat():
    '''Test CollectionContact functionality.'''
    getter = CollectionConcat(collections=[
        'fooz',
        SuffixFilter('barz', '.c')
    ])

    result = getter(artefact_store={
        'fooz': ['foo1', 'foo2'],
        'barz': [Path('bar.a'), Path('bar.b'), Path('bar.c')],
    })

    assert result == ['foo1', 'foo2', Path('bar.c')]
