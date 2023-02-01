# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from fab.steps.grab.svn import SvnCheckout, SvnExport, SvnMerge


class FcmExport(SvnExport):
    command = 'fcm'


class FcmCheckout(SvnCheckout):
    command = 'fcm'


class FcmMerge(SvnMerge):
    command = 'fcm'
