##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
import os
from argparse import ArgumentParser

from fab.build_config import BuildConfig
from fab.steps.grab import GrabFcm


def gcom_grab_config(revision=None):
    """
    Grab the gcom source, for use by multiple rose build configs.

    """
    return BuildConfig(
        project_label=f'gcom_source_{revision}',
        steps=[
            GrabFcm(src=f'fcm:gcom.xm_tr/build', revision=revision, dst_label="gcom"),
        ])


if __name__ == '__main__':
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--revision', default=os.getenv('GCOM_REVISION', 'vn7.6'))
    args = arg_parser.parse_args()

    logging.getLogger('fab').setLevel(logging.DEBUG)
    gcom_grab_config(revision=args.revision).run()
