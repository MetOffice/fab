#!/usr/bin/env python3
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from fab.build_config import BuildConfig
from fab.steps.grab.fcm import fcm_export


LFRIC_REVISION = 40984


# these configs are interrogated by the build scripts
lfric_source_config = BuildConfig(project_label=f'lfric source {LFRIC_REVISION}')
gpl_utils_source_config = BuildConfig(project_label=f'lfric source {LFRIC_REVISION}')


if __name__ == '__main__':

    with lfric_source_config:
        fcm_export(
            lfric_source_config, src='fcm:lfric.xm_tr', revision=LFRIC_REVISION, dst_label='lfric')

    with gpl_utils_source_config:
        fcm_export(
            gpl_utils_source_config, src='fcm:lfric_gpl_utils.xm-tr', revision=LFRIC_REVISION, dst_label='gpl_utils')
