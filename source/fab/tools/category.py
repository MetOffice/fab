##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This simple module defines an Enum for all allowed categories.
'''

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
    allows iterating over all catogories, e.g. `for cat in Categories`.

    The category adds `__hash__` and `__eq__`, which allows it to be
    used as keys in dictionaries (e.g. `ToolBox`) and comparisons.
    """

    def __new__(cls, name: str, val: Optional[int] = None):
        # choose a numeric value for the int part
        if val is not None:
            # Called via __reduce__ (i.e. pickle), restore
            # the original int value
            obj = super().__new__(cls, val)
        else:
            # New name. Verify that it doesn't exist yet
            if name in cls._values:
                raise ValueError(f"Category '{name}' already exists.")
            # Get a new id for the name. Use +1 to avoid using a zero
            # (just in case)
            obj = super().__new__(cls, len(cls._values) + 1)
        cls._values[name] = obj
        return obj

    def __reduce__(self):
        # return (callable, args) so pickle can reconstruct the object
        return (Category, (self._name, int(self)))

    def __init__(self, name: str, int: Optional[int] = None):
        # Store the name for the name attribute, and create
        # an attribute with the same name
        self._name = name
        setattr(Category, name, self)

    def __str__(self):
        return self._name

    def __hash__(self):
        return hash(self._name)

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
    AR: "Category"
    C_COMPILER: "Category"
    C_PREPROCESSOR: "Category"
    FCM: "Category"
    FORTRAN_COMPILER: "Category"
    FORTRAN_PREPROCESSOR: "Category"
    GIT: "Category"
    LINKER: "Category"
    MISC: "Category"
    PSYCLONE: "Category"
    RSYNC: "Category"
    SHELL: "Category"
    SUBVERSION: "Category"


# Now create the default categories that Fab needs
Category("AR")
Category("C_COMPILER")
Category("C_PREPROCESSOR")
Category("FCM")
Category("FORTRAN_COMPILER")
Category("FORTRAN_PREPROCESSOR")
Category("GIT")
Category("LINKER")
Category("MISC")
Category("PSYCLONE")
Category("RSYNC")
Category("SHELL")
Category("SUBVERSION")
