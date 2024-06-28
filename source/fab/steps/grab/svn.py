# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Contains the steps related to Subversion. It is also used by the various
FCM steps, which call the functions here with just a different category (FCM)
from the tool box.
"""

from pathlib import Path
from typing import Optional, Union, Tuple
import xml.etree.ElementTree as ET

from fab.build_config import BuildConfig
from fab.steps import step
from fab.tools import Category, Subversion, Tool, Versioning


def split_repo_url(url: str,
                   revision: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Pull out the revision if it's part of the url.

    Some operations need it separated from the url,
    e.g. when calling fcm update, which accepts revision but no url.

    :param url: Repository url.
    :param revision: Expected revision or None.
    :return: URL and revision.
    """
    url_revision = None
    at_split = url.split('@')
    if len(at_split) == 2:
        url_revision = at_split[1]
        if url_revision and revision and url_revision != revision:
            raise ValueError('Conflicting revisions in url and argument. '
                             'Please provide as argument only.')
        url = at_split[0]
    else:
        assert len(at_split) == 1

    return url, revision or url_revision


def _svn_prep_common(config: BuildConfig, src: str,
                     dst_label: Optional[str],
                     revision: Optional[str]) -> Tuple[str, Path,
                                                       Optional[str]]:
    src, revision = split_repo_url(src, revision)
    if not config.source_root.exists():
        config.source_root.mkdir(parents=True, exist_ok=True)
    dst: Path = config.source_root / (dst_label or '')

    return src, dst, revision


@step
def svn_export(config: BuildConfig, src: str,
               dst_label: Optional[str] = None,
               revision: Optional[str] = None,
               category=Category.SUBVERSION):
    # todo: params in docstrings
    """
    Export an FCM repo folder to the project workspace.

    """
    svn = config.tool_box[category]
    assert isinstance(svn, Subversion)  # ToDo: Better way to handle classes.
    src, dst, revision = _svn_prep_common(config, src, dst_label, revision)
    svn.export(src, dst, revision)


@step
def svn_checkout(config: BuildConfig,
                 src: str, dst_label: Optional[str] = None,
                 revision: Optional[str] = None,
                 category=Category.SUBVERSION) -> None:
    """
    Checkout or update an FCM repo.

    .. note::
        If the destination is a working copy, it will be updated to the given
        revision, **ignoring the source url**. As such, the revision should
        be provided via the argument, not as part of the url.

    """
    svn = config.tool_box[category]
    assert isinstance(svn, Subversion)  # ToDo: Better way to handle classes.
    src, dst, revision = _svn_prep_common(config, src, dst_label, revision)

    # new folder?
    if not dst.exists():  # type: ignore
        svn.checkout(src, dst, revision)
    else:
        # update
        # todo: ensure the existing checkout is from self.src?
        svn.update(dst, revision)


def svn_merge(config: BuildConfig,
              src: str, dst_label: Optional[str] = None,
              revision: Optional[str] = None,
              category=Category.SUBVERSION):
    """
    Merge an FCM repo into a local working copy.

    """
    svn = config.tool_box[category]
    assert isinstance(svn, Subversion)  # ToDo: Better way to handle classes.
    src, dst, revision = _svn_prep_common(config, src, dst_label, revision)

    svn.merge(src, dst, revision)
    check_conflict(svn, dst)


def check_conflict(tool: Tool, dst: Union[str, Path]) -> bool:
    """
    Check if there's a conflict
    """
    assert isinstance(tool, Versioning)  # ToDo: Better way to handel classes.
    xml_str = tool.run(['status', '--xml'], cwd=dst, capture_output=True)
    root = ET.fromstring(xml_str)

    for target in root:
        if target.tag != 'target':
            continue
        for entry in target:
            if entry.tag != 'entry':
                continue
            for element in entry:
                if (element.tag == 'wc-status' and
                        element.attrib['item'] == 'conflicted'):
                    raise RuntimeError(f'{tool} merge encountered a '
                                       f'conflict:\n{xml_str}')
    return False
