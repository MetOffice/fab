##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This module tests the Categories.
'''

from fab.tools.category import Category


def test_category():
    '''Tests the categories.'''
    # Make sure that str of a category only prints the name (which is more
    # useful for error messages).
    for cat in list(Category):
        assert str(cat) == cat.name


def test_is_compiler():
    '''Tests that compiler correctly sets the `is_compiler` property.'''
    for cat in Category:
        if cat in [Category.FORTRAN_COMPILER, Category.C_COMPILER]:
            assert cat.is_compiler
        else:
            assert not cat.is_compiler
