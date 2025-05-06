# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Exercises grab from Subversion and FCM steps.

Most of the testing happens at the task level.

ToDo: Messing with "private" members.
"""
from typing import Optional, Tuple

from pytest import mark, raises

from fab.steps.grab.svn import _get_revision


class TestRevision(object):
    """
    Tests handling of revisions.
    """
    @mark.parametrize(
        ['url', 'expected'],
        [
            ('http://example.net/repo', ('http://example.net/repo', None)),
            ('http://example.net/repo@rev', ('http://example.net/repo', 'rev'))
        ]
    )
    def test_no_revision(self, url: str,
                         expected: Tuple[str, Optional[str]]) -> None:
        """
        Tests revision argument not given.
        """
        assert _get_revision(src=url) == expected

    @mark.parametrize(
        ['url', 'revision', 'expected'],
        [
            ('http://example.net/repo', 'rev', ('http://example.net/repo', 'rev')),
            ('http://example.net/repo@rev', 'rev', ('http://example.net/repo', 'rev'))
        ]
    )
    def test_revision_param(self, url: str, revision: str,
                            expected: Tuple[str, Optional[str]]):
        """
        Tests revision argument given.
        """
        assert _get_revision(src=url, revision=revision) == expected

    def test_both_different(self):
        """
        Tests mismatch between URL revision and argument.
        """
        with raises(ValueError):
            assert _get_revision(src='url@rev', revision='bez')
