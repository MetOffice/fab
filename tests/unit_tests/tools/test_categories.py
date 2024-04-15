##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This module tests the Categories.
'''

from fab.newtools import Categories


def test_categories():
    '''Tests the categories.'''
    # Make sure that str of a category only prints the name (which is more
    # useful for error messages).
    for cat in list(Categories):
        assert str(cat) == cat.name
