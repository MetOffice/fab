##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Example of an app-specific default config class.
"""

# Mypy does not handle the relative import here properly, ignore error:
from site_specific.default.config import Config as ConfigSiteDefault   # type: ignore


class Config(ConfigSiteDefault):

    def __str__(self):
        """
        This str method also collects the call-order.
        """
        return f"{super().__str__()} -> AppSpecificDefault"
