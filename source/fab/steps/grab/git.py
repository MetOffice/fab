# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''This module contains the git related steps.
'''

import warnings

from fab.steps import step
from fab.tools import Category


# todo: allow cli args, e.g to set the depth
@step
def git_checkout(config, src: str, dst_label: str = '', revision=None):
    """
    Checkout or update a Git repo.

    """
    git = config.tool_box[Category.GIT]
    dst = config.source_root / dst_label

    # create folder?
    if not dst.exists():
        dst.mkdir(parents=True)
        git.init(dst)

    git.checkout(src, dst, revision=revision)
    try:
        dst.relative_to(config.project_workspace)
        git.clean(dst)
    except RuntimeError:
        warnings.warn(f'not safe to clean git source in {dst}')


@step
def git_merge(config, src: str, dst_label: str = '', revision=None):
    """
    Merge a git repo into a local working copy.

    """
    git = config.tool_box[Category.GIT]
    dst = config.source_root / dst_label
    git.fetch(src=src, dst=dst, revision=revision)
    git.merge(dst=dst, revision=revision)
