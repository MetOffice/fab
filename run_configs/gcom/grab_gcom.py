#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import os
from argparse import ArgumentParser

from fab.build_config import BuildConfig
from fab.steps.grab.fcm import FcmExport


def gcom_grab_config(revision=None):
    """
    Grab the gcom source.

    """
    return BuildConfig(
        project_label=f'gcom_source_{revision}',
        steps=[
            FcmExport(src='fcm:gcom.xm_tr/build', revision=revision, dst="gcom"),
        ])


if __name__ == '__main__':
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--revision', default=os.getenv('GCOM_REVISION', 'vn7.6'))
    args = arg_parser.parse_args()

    gcom_grab_config(revision=args.revision).run()
