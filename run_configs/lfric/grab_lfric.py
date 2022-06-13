#!/usr/bin/env python3
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from fab.build_config import BuildConfig
from fab.steps.grab import GrabFcm, GrabSvn


def lfric_source_config():
    return BuildConfig(
        project_label='lfric source',
        steps=[GrabFcm(src='fcm:lfric.xm_tr', dst_label='lfric')]
    )


def gpl_utils_source_config():
    return BuildConfig(
        project_label='lfric source',
        steps=[GrabSvn(src='https://code.metoffice.gov.uk/svn/lfric/GPL-utilities/trunk', dst_label='gpl_utils')]
    )


def other_projects_source_config():
    # for building atm
    return BuildConfig(
        project_label='lfric source',
        steps=[
            GrabFcm(src='fcm:um.xm_tr/src', dst_label='um', revision=109936),
            GrabFcm(src='fcm:jules.xm_tr/src', dst_label='jules', revision=23182),
            GrabFcm(src='fcm:socrates.xm_tr/src', dst_label='socrates', revision='um12.2'),
            GrabFcm(src='fcm:casim.xm_tr/src', dst_label='casim', revision='um12.2'),
            GrabFcm(src='fcm:shumlib.xm_tr/', dst_label='shumlib', revision='um12.2'),
        ]
    )


if __name__ == '__main__':
    lfric_source_config().run()
    gpl_utils_source_config().run()
    other_projects_source_config().run()
