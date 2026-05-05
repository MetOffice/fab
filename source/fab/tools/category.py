##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This simple module defines an Enum for all allowed categories.
'''

from __future__ import annotations

from typing import Optional


class CategoryMeta(type):
    """
    A meta class for a simple, enum-like Category class,
    that provides an API to allow to iterate over all categories.
    """

    # A dictionary used for iterating over all enums.
    _values: dict[str, "Category"] = {}

    def __iter__(cls):
        return iter(cls._values.values())


class Category(int, metaclass=CategoryMeta):
    """
    This class defines the allowed tool categories. It presents
    an interface similar to a Python enum, but it allows to extend
    an enum.

    A enum is created by just creating an instance, e.g.:
    `Category("PSYCLONE")` (and it is checked that all names
    are unique). This will create `Category.PSYCLONE`. It also
    allows iterating over all categories, e.g. `for cat in Categories`.

    """

    def __new__(cls, name: str, val: Optional[int] = None):
        # choose a numeric value for the int part
        if val is not None:
            # Called via __reduce__ (i.e. pickle), restore
            # the original int value
            obj = super().__new__(cls, val)
        # New name. If it already exists, return the existing
        # object
        elif name in cls._values:
            obj = cls._values[name]
        else:
            # Get a new id for the name. Use +1 to avoid using a zero
            # (just in case)
            obj = super().__new__(cls, len(cls._values) + 1)
            cls._values[name] = obj

        return obj

    def __reduce__(self):
        # return (callable, args) so pickle can reconstruct the object
        return (Category, (self._name, int(self)))

    def __init__(self, name: str, value: Optional[int] = None):
        """
        Creates the instance, and also sets it as class attribute of the
        Category class. The `value` parameter is only required for
        pickling (which is used when starting sub-processes)/

        :param name: The name of the category to create, which will also
            become an attribute of Category.
        :param value: the integer value (which will be set in __new__,
            and is otherwise required for pickling only).
        """
        # Store the name for the name attribute, and create
        # an attribute with the same name
        self._name = name
        setattr(Category, name, self)

    @staticmethod
    def add(name: str) -> None:
        """
        Adds a new category.
        """
        # We don't need to store the instance, it is added as an attribute
        # to this class anyway.
        Category(name)

    def __str__(self):
        return self._name

    @property
    def name(self) -> str:
        """
        Compatibility to enum feature:

        :returns: the name of this Category as string.
        """
        return self._name

    @property
    def is_compiler(self) -> bool:
        """
        :returns: if this Category is a Fortran or C compiler.
        """
        return self in [Category.C_COMPILER,
                        Category.FORTRAN_COMPILER]

    # We need to declare all attributes here, otherwise mypy
    # is not happy. The actual values will be set below (we cannot
    # call the Category constructor here)
    AR: Category
    C_COMPILER: Category
    C_PREPROCESSOR: Category
    FCM: Category
    FORTRAN_COMPILER: Category
    FORTRAN_PREPROCESSOR: Category
    GIT: Category
    LINKER: Category
    PSYCLONE: Category
    RSYNC: Category
    SHELL: Category
    SUBVERSION: Category
    # In order to make mypy happy, we add this category for
    # unit tests.
    CATEGORY_FOR_UNIT_TESTS: Category


# Now create the default categories that Fab needs
Category.add("C_COMPILER")
Category.add("C_PREPROCESSOR")
Category.add("FORTRAN_COMPILER")
Category.add("FORTRAN_PREPROCESSOR")
Category.add("LINKER")
