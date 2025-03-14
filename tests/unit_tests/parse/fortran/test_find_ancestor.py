# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''Test the find_ancestor function.
'''

from fab.parse.fortran import FortranAnalyser


class Thing1():
    # pylint: disable=too-few-public-methods
    '''A dummy class mirroring the fparser design - have a parent attribute.'''
    def __init__(self, parent):
        self.parent = parent


class Thing2(Thing1):
    # pylint: disable=too-few-public-methods
    '''Dummy class for testing.'''


class TestFindAncestor():
    '''Test the find_ancerstor functionality of the FortranAnalyser.'''

    def test_true(self):
        '''Test to successfully find the class'''
        t2 = Thing2(None)
        thing = Thing1(parent=Thing1(parent=t2))
        # Test that it evaluates to true, and also that it is the right type
        assert FortranAnalyser._find_ancestor(thing, Thing2)
        assert FortranAnalyser._find_ancestor(thing, Thing2) is t2

        # Test searching for more than one class.
        assert FortranAnalyser._find_ancestor(thing, (Thing1, Thing2))
        # Since thing is a Thing1, it will be returned itself
        assert FortranAnalyser._find_ancestor(thing, (Thing1, Thing2)) is thing

    def test_false(self):
        '''Test if the class is not found.'''
        thing = Thing1(parent=Thing1(parent=Thing1(None)))
        assert not FortranAnalyser._find_ancestor(thing, Thing2)
