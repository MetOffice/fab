# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''This file contains the various fcm steps. They are not
decorated with @steps since all functions here just call the
corresponding svn steps.
'''

from typing import Optional

from fab.steps.grab.svn import svn_export, svn_checkout, svn_merge
from fab.tools import Categories


def fcm_export(config, src: str, dst_label: Optional[str] = None,
               revision: Optional[str] = None):
    """
    Params as per :func:`~fab.steps.grab.svn.svn_export`.

    """
    svn_export(config, src, dst_label, revision, category=Categories.FCM)


def fcm_checkout(config, src: str, dst_label: Optional[str] = None,
                 revision: Optional[str] = None):
    """
    Params as per :func:`~fab.steps.grab.svn.svn_checkout`.

    """
    svn_checkout(config, src, dst_label, revision, category=Categories.FCM)


def fcm_merge(config, src: str, dst_label: Optional[str] = None,
              revision: Optional[str] = None):
    """
    Params as per :func:`~fab.steps.grab.svn.svn_merge`.

    """
    svn_merge(config, src, dst_label, revision, category=Categories.FCM)
