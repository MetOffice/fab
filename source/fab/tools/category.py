##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This simple module defines an Enum for all allowed categories.
'''


class CategoryMeta(type):
    """
    A meta class for a simple, enum-like Category class,
    that provides an API to allow to iterate over all categories.
    """

    def __iter__(cls):
        return iter(cls._values.values())


class Category(metaclass=CategoryMeta):
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

    _values: dict[str, "Category"] = {}

    def __init__(self, name: str):
        if name in Category._values:
            raise ValueError(f"Category '{name}' already exists.")
        self._name = name
        Category._values[name] = self
        setattr(Category, name, self)

    def __str__(self):
        return self._name

    def __hash__(self):
        return hash(self._name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Category) and self._name == other._name

    @property
    def name(self) -> str:
        """
        :returns: the name of this Category as string.
        """
        return self._name

    @property
    def is_compiler(self) -> bool:
        """
        :returns: if this Category is a Fortran or C compiler.
        """
        return self in [Category._values["C_COMPILER"],
                        Category._values["FORTRAN_COMPILER"]]

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
