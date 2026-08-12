##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Example of an app- and site-specific default config class.
"""

# Mypy does not handle the relative import here properly, ignore error:
from app_specific.default.config import Config as ConfigAppDefault   # type: ignore
from site_specific.site_platform.config import Config as ConfigSiteSitePlatform   # type: ignore


class Config(ConfigAppDefault, ConfigSiteSitePlatform):
    """A simple app-specific configuration for a specific site/platform.
    It inherits from both the default app-specific config and the
    site-specific configuration. The order of the base classes is important
    to achieve the expected call sequence across all classes:
    this -> AppSpecificDefault -> SiteSpecificConfig -> SiteSpecificDefault
    """

    def __str__(self):
        """
        This str method also collects the call-order.
        """
        return f"AppSpecificSitePlatform -> {super().__str__()}"
