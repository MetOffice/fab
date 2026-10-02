#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from fab.api import BuildConfig, fcm_export, ToolBox


revision = 'vn7.6'

# we put this here so the two build configs can read its source_root
grab_config = BuildConfig(project_label=f'gcom_source {revision}',
                          tool_box=ToolBox())


if __name__ == '__main__':

    # note: we can add arguments to grab_config.arg_parser here
    # todo: do a real example of this in one of the configs, or at least in the docs.

    with grab_config:
        fcm_export(grab_config, src='fcm:gcom.xm_tr/build', revision=revision, dst_label="gcom")
