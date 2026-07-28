"""
A location for methods used in configuration of the build. These are to be as
generic as possible, and can be used by both build_script and database.
"""

from typing import Any


class WriteOnceDict(dict):
    """
    A write once dictionary. Users cannot add the same key, or use the delete function.
    """

    def __delitem__(self, key: str):
        raise KeyError("Read-only dictionary")

    def __setitem__(self, key: str, value: Any):
        if key in self:
            raise KeyError(f"{key} has already been set")
        super().__setitem__(key, value)
