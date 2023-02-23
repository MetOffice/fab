# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from fab.steps.grab.git import get_remotes


class Test_get_remotes(object):

    def test(self):
        result = get_remotes()
        assert 'origin' in result
        assert '/fab.git' in result['origin']


