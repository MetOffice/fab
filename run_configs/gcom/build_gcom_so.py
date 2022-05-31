#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import os
from argparse import ArgumentParser

from fab.steps.link_exe import LinkSharedObject

from fab.build_config import BuildConfig
from gcom_build_steps import common_build_steps
from grab_gcom import gcom_grab_config


def gcom_so_config(revision=None):
    """
    Create a shared object for linking.

    """
    config = BuildConfig(
        project_label=f'gcom shared library {revision}',
        source_root=gcom_grab_config(revision=revision).source_root,
        steps=[
            *common_build_steps(fpic=True),
            LinkSharedObject(linker='mpifort', output_fpath='$output/libgcom.so'),
        ]
    )

    return config


if __name__ == '__main__':
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--revision', default=os.getenv('GCOM_REVISION', 'vn7.6'))
    args = arg_parser.parse_args()

    gcom_so_config(revision=args.revision).run()
