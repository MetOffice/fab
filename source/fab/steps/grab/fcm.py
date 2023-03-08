# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from typing import Optional

from fab.steps.grab.svn import svn_export, SvnCheckout, SvnMerge




def fcm_export(config, src: str, dst: Optional[str] = None, revision=None):
    """
    Params as per :func:`~fab.steps.svn.svn_export`.

    """
    svn_export(config, src, dst, revision, tool='fcm')


class FcmCheckout(SvnCheckout):
    command = 'fcm'


class FcmMerge(SvnMerge):
    command = 'fcm'
