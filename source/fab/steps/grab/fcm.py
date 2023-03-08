# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from typing import Optional

from fab.steps.grab.svn import svn_export, svn_checkout, svn_merge


def fcm_export(config, src: str, dst_label: Optional[str] = None, revision=None):
    """
    Params as per :func:`~fab.steps.svn.svn_export`.

    """
    svn_export(config, src, dst_label, revision, tool='fcm')


def fcm_checkout(config, src: str, dst_label: Optional[str] = None, revision=None):
    """
    Params as per :func:`~fab.steps.svn.svn_checkout`.

    """
    svn_checkout(config, src, dst_label, revision, tool='fcm')


def fcm_merge(config, src: str, dst_label: Optional[str] = None, revision=None):
    """
    Params as per :func:`~fab.steps.svn.svn_merge`.

    """
    svn_merge(config, src, dst_label, revision, tool='fcm')
