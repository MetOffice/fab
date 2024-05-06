# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

import warnings

from fab.steps import step
from fab.newtools import Categories


# todo: allow cli args, e.g to set the depth
@step
def git_checkout(config, src: str, dst_label: str = '', revision=None):
    """
    Checkout or update a Git repo.

    """
    git = config.tool_box[Categories.GIT]
    dst = config.source_root / dst_label

    # create folder?
    if not dst.exists():
        dst.mkdir(parents=True)
        git.run(['init', '.'], cwd=dst)
    elif not git.is_working_copy(dst):  # type: ignore
        raise ValueError(f"destination exists but is not a working copy: '{dst}'")

    git.fetch(src, dst, revision=revision)
    git.checkout(src, dst, revision=revision)
    try:
        dst.relative_to(config.project_workspace)
        git.run(['clean', '-f'], cwd=dst)
    except RuntimeError:
        warnings.warn(f'not safe to clean git source in {dst}')


@step
def git_merge(config, src: str, dst_label: str = '', revision=None):
    """
    Merge a git repo into a local working copy.

    """
    git = config.tool_box[Categories.GIT]
    dst = config.source_root / dst_label
    git.merge(dst, src=src, revision=revision)
    git.fetch(src=src, revision=revision, dst=dst)
    git.merge(dst=dst, src=src, revision=revision)
