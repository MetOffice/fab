"""
Fab API interface.

This module allows the user-facing functionality of the Fab build
system to be imported in a single operation.  The module decouples the
imports from the location of individual modules and adds versioning to
allow breaking changes to the API to be managed.
"""

from .v3 import *
from .v3 import __all__ as __v3_all__
from .v3 import __version__  # noqa: F401

__all__ = tuple(__v3_all__)
