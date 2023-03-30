# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import warnings
from pathlib import Path
from typing import Union

from fab.steps import step
from fab.tools import run_command


def current_commit(folder=None):
    folder = folder or '.'
    output = run_command(['git', 'log', '--oneline', '-n', '1'], cwd=folder)
    commit = output.split()[0]
    return commit


def tool_available() -> bool:
    """Is the command line git tool available?"""
    try:
        run_command(['git', 'help'])
    except FileNotFoundError:
        return False
    return True


def is_working_copy(dst: Union[str, Path]) -> bool:
    """Is the given path is a working copy?"""
    try:
        run_command(['git', 'status'], cwd=dst)
    except RuntimeError:
        return False
    return True


def fetch(src, revision, dst):
    # todo: allow shallow fetch with --depth 1
    command = ['git', 'fetch', src]
    if revision:
        command.append(revision)

    run_command(command, cwd=str(dst))


# todo: allow cli args, e.g to set the depth
@step
def git_checkout(config, src: str, dst_label: str = '', revision=None):
    """
    Checkout or update a Git repo.

    """
    _dst = config.source_root / dst_label

    # create folder?
    if not _dst.exists():
        _dst.mkdir(parents=True)
        run_command(['git', 'init', '.'], cwd=_dst)

    elif not is_working_copy(_dst):  # type: ignore
        raise ValueError(f"destination exists but is not a working copy: '{_dst}'")

    fetch(src, revision, _dst)
    run_command(['git', 'checkout', 'FETCH_HEAD'], cwd=_dst)

    try:
        _dst.relative_to(config.project_workspace)
        run_command(['git', 'clean', '-f'], cwd=_dst)
    except ValueError:
        warnings.warn(f'not safe to clean git source in {_dst}')


@step
def git_merge(config, src: str, dst_label: str = '', revision=None):
    """
    Merge a git repo into a local working copy.

    """
    _dst = config.source_root / dst_label

    if not _dst or not is_working_copy(_dst):
        raise ValueError(f"destination is not a working copy: '{_dst}'")

    fetch(src=src, revision=revision, dst=_dst)

    try:
        run_command(['git', 'merge', 'FETCH_HEAD'], cwd=_dst)
    except RuntimeError as err:
        run_command(['git', 'merge', '--abort'], cwd=_dst)
        raise RuntimeError(f"Error merging {revision}. Merge aborted.\n{err}")
