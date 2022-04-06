##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Flexible build system for scientific software.

"""
import logging
import sys

__version__ = '2022.1.dev0'

logging.getLogger(__name__).addHandler(logging.StreamHandler(sys.stdout))


class FabException(Exception):
    pass
