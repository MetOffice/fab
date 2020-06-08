##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Classes for accessing source stored in repositories.

The term "repository" is drawn quite widely here. It includes not only version
control repositories but also archive files on disc. It also considers ways of
accessing those repositories such as rsync and FTP.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from subprocess import run
from urllib.parse import urlparse

from fab import FabException


class Repository(ABC):
    """
    All mechanisms for obtaining source trees inherit from this abstract class.
    """
    def __init__(self, url: str):
        self._url = url

    @property
    def url(self) -> str:
        return self._url

    @abstractmethod
    def extract(self, target: Path):
        """
        Extracts the source tree to the supplied path. The source is fetched
        from the URL provided at construction.
        """
        raise NotImplementedError("Abstract methods must be implemented.")


class SubversionRepo(Repository):
    """
    Extracts a source tree from a Subversion repository.

    This class currently wraps the Subversion command-line client but that may
    prove unsatisfactory. In particular it could be too slow. In that case we
    should examine the possibility of using the Python bindings provided with
    Subversion.
    """
    def __init__(self, url: str):
        super().__init__(url)

    def extract(self, target: Path):
        target.parent.mkdir(parents=True, exist_ok=True)
        command = ['svn', 'export', '--force', self.url, str(target)]
        report = run(command)
        if report.returncode != 0:
            message = f"Unable to extract Subversion repository: {self.url}"
            raise FabException(message)


def repository_from_url(url: str) -> Repository:
    """
    Creates an appropriate Repository object from a given URL.

    TODO: This will need to be considerably more elaborate in the future once
          we get multiple repository types on a given scheme. e.g. Both
          Subversion and Git may be accessed using HTTP URLs. Likewise both
          Subversion and file trees on disc may be accessed using "file" URLs.
    """
    url_components = urlparse(url)
    if url_components.scheme not in ('file', 'http', 'https', 'svn'):
        message = "Unrecognised scheme '{scheme}' for Subversion repository"
        raise FabException(message.format(scheme=url_components.scheme))
    return SubversionRepo(url)
