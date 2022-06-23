from unittest import mock
from unittest.mock import call

import pytest

from fab.constants import BUILD_TREES

from fab.artefacts import FilterBuildTrees


class TestFilterBuildTrees(object):

    @pytest.fixture
    def artefact_store(self):
        return {
            BUILD_TREES: {
                'tree1': {
                    'a.foo': None,
                    'b.foo': None,
                    'c.bar': None,
                },
                'tree2': {
                    'd.foo': None,
                    'e.foo': None,
                    'f.bar': None,
                },
            }
        }

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
