# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Contains the git related steps.
"""
from pathlib import Path
from typing import Optional
import warnings

from fab.build_config import BuildConfig
from fab.steps import step
from fab.tools import Category, Git


# todo: allow cli args, e.g to set the depth
@step
def git_checkout(config: BuildConfig,
                 src: Path,
                 dst_label: str = '',
                 revision: Optional[str] = None):
    """
    Checkout or update a Git repo.
    """
    git = config.tool_box[Category.GIT]
    assert isinstance(git, Git)  # ToDo: Problem with typing.
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
def git_merge(config: BuildConfig,
              src: Path, dst_label: str = '', revision: Optional[str] = None):
    """
    Merges a git repository into a local working copy.
    """
    git = config.tool_box[Category.GIT]
    assert isinstance(git, Git)  # ToDo: Problem with typing.
    dst = config.source_root / dst_label
    git.fetch(src=src, dst=dst, revision=revision)
    git.merge(dst=dst, revision=revision)
