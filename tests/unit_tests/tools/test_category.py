##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
This module tests the Categories.
"""

import pickle

from pytest import raises


from fab.tools.category import Category


def test_duplicate_categories():
    """
    Tests that we get an error if we try to duplicate a category.
    """

    with raises(ValueError) as err:
        Category("FORTRAN_COMPILER")

    assert "Category 'FORTRAN_COMPILER' already exists." in str(err.value)


def test_hash():
    """
    Test the hash functionality.
    """

    assert hash(Category.FORTRAN_COMPILER) == hash("FORTRAN_COMPILER")


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


def test_category_pickle():
    """
    Test that pickling will return an object with the same
    integer representation.
    """

    c = Category.AR
    data = pickle.dumps(c)
    c2 = pickle.loads(data)
    assert c2 == c
