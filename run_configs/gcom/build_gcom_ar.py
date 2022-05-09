##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
import os
from argparse import ArgumentParser

from fab.build_config import BuildConfig
from fab.steps.archive_objects import ArchiveObjects
from gcom_build_steps import common_build_steps
from grab_gcom import gcom_grab_config


def gcom_ar_config(revision=None):
    """
    Create an object archive for linking.

    """
    config = BuildConfig(
        project_label=f'gcom object archive {revision}',
        source_root=gcom_grab_config(revision=revision).source_root
    )

    config.steps = [
        *common_build_steps(),
        ArchiveObjects(output_fpath='$output/libgcom.a'),
    ]

    return config


if __name__ == '__main__':
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--revision', default=os.getenv('GCOM_REVISION', 'vn7.6'))
    args = arg_parser.parse_args()

    # logging.getLogger('fab').setLevel(logging.DEBUG)
    gcom_ar_config(revision=args.revision).run()
