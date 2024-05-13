# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Known command line tools whose flags we wish to manage.

"""
import logging
from typing import List

from fab.util import string_checksum

logger = logging.getLogger(__name__)


def flags_checksum(flags: List[str]):
    """
    Return a checksum of the flags.

    """
    return string_checksum(str(flags))
