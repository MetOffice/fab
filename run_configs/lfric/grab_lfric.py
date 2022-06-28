#!/usr/bin/env python3
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from fab.build_config import BuildConfig
from fab.steps.grab import GrabFcm, GrabSvn


LFRIC_REVISION = 36615


def lfric_source_config(revision=LFRIC_REVISION):
    return BuildConfig(
        project_label=f'lfric source {revision}',
        steps=[GrabFcm(src='fcm:lfric.xm_tr', revision=revision, dst_label='lfric')]
    )


def gpl_utils_source_config(revision=LFRIC_REVISION):
    return BuildConfig(
        project_label=f'lfric source {revision}',
        steps=[GrabSvn(src='https://code.metoffice.gov.uk/svn/lfric/GPL-utilities/trunk',
                       revision=revision, dst_label='gpl_utils')]
    )


if __name__ == '__main__':

    lfric_source_config().run()
    gpl_utils_source_config().run()
