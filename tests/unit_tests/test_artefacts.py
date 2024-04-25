from unittest import mock
from unittest.mock import call

import pytest

from fab.artefacts import ArtefactStore, ArtefactsGetter, FilterBuildTrees
from fab.constants import BUILD_TREES, CURRENT_PREBUILDS


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

    @pytest.fixture
    def artefact_store(self):
        '''A fixture that returns an ArtefactStore with
        some elements.'''
        artefact_store = ArtefactStore()
        artefact_store[BUILD_TREES] = {'tree1': {'a.foo': None,
                                                 'b.foo': None,
                                                 'c.bar': None, },
                                       'tree2': {'d.foo': None,
                                                 'e.foo': None,
                                                 'f.bar': None, },
                                       }
        return artefact_store

    def test_single_suffix(self, artefact_store):
        # ensure the artefact getter passes through the trees properly to the filter func

        # run the artefact getter
        filter_build_trees = FilterBuildTrees('.foo', BUILD_TREES)
        with mock.patch('fab.artefacts.filter_source_tree') as mock_filter_func:
            filter_build_trees(artefact_store)

        mock_filter_func.assert_has_calls([
            call(source_tree=artefact_store[BUILD_TREES]['tree1'], suffixes=['.foo']),
            call(source_tree=artefact_store[BUILD_TREES]['tree2'], suffixes=['.foo']),
        ])

    def test_multiple_suffixes(self, artefact_store):
        # test it works with multiple suffixes provided
        filter_build_trees = FilterBuildTrees(['.foo', '.bar'], BUILD_TREES)
        with mock.patch('fab.artefacts.filter_source_tree') as mock_filter_func:
            filter_build_trees(artefact_store)

        mock_filter_func.assert_has_calls([
            call(source_tree=artefact_store[BUILD_TREES]['tree1'], suffixes=['.foo', '.bar']),
            call(source_tree=artefact_store[BUILD_TREES]['tree2'], suffixes=['.foo', '.bar']),
        ])


def test_artefact_store():
    '''Tests the ArtefactStore class.'''
    artefact_store = ArtefactStore()
    assert len(artefact_store) == 1
    assert isinstance(artefact_store, dict)
    assert CURRENT_PREBUILDS in artefact_store
