##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Example of an site_specific non-default config class.
"""

# Mypy does not handle the relative import here properly, ignore error:
from site_specific.default.config import Config as ConfigSiteDefault   # type: ignore


class Config(ConfigSiteDefault):
    """A simple site-specific configuration for a given site/platform.
    It inherits from the site-specific default configuration.
    """

    def __str__(self) -> str:
        """
        This str method also collects the call-order.
        """
        return f"SiteSpecificSitePlatform -> {super().__str__()}"
