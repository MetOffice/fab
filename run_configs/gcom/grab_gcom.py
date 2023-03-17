#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from contextlib import contextmanager

from fab.build_config import build_config
from fab.steps.grab.fcm import fcm_export


revision = 'vn7.6'


# This is a context manager because we want to return just the config, for use in the two build scripts.
# They use this to get the source folder, rather than having to work it out.
# Since build_config is itself a context manager, so must this be.
@contextmanager
def gcom_grab_config():
    with build_config(project_label=F'gcom_source {revision}') as config:
        yield config


if __name__ == '__main__':

    with gcom_grab_config() as config:
        fcm_export(config, src='fcm:gcom.xm_tr/build', revision=revision, dst_label="gcom")
