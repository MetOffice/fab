"""
Fab API interface.

This module allows the user-facing functionality of the Fab build
system to be imported in a single operation.  The module decouples the
imports from the location of individual modules and adds versioning to
allow breaking changes to the API to be managed.
"""

from .v2 import *
from .v2 import VERSION  # noqa: F401
from .v2 import __all__ as __v2_all__

__all__ = tuple(__v2_all__)
