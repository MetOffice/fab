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
from subprocess import PIPE, Popen, run
import tarfile
from urllib.parse import urlparse, urlunparse

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
            if report.stderr is not None:
                message += '\n' + str(report.stderr)
            raise FabException(message)


class GitRepo(Repository):
    """
    Extracts a source tree from a Git repository.

    This class currently wraps the Git command-line client but that may prove
    unsatisfactory. In particular it could be too slow. In that case we should
    find out if there are Python bindings for Git.
    """
    _TIMEOUT = 4.0  # Seconds

    def __init__(self, url: str):
        super().__init__(url)

    def extract(self, target: Path):
        target.parent.mkdir(parents=True, exist_ok=True)
        command = ['git', 'archive', '--format=tar',
                   '--remote='+self.url, 'HEAD']
        process = Popen(command, stdout=PIPE)
        archive = tarfile.open(fileobj=process.stdout, mode='r|')
        archive.extractall(target)
        process.wait(self._TIMEOUT)
        if process.returncode != 0:
            message = f"Unable to extract Git repository: {self.url}"
            if process.stderr is not None:
                message += '\n' + str(process.stderr)
            raise FabException(message)


def repository_from_url(url: str) -> Repository:
    """
    Creates an appropriate Repository object from a given URL.

    An extended syntax is used for the URL scheme: <vcs>+<protocol>.

    So to access a Subversion repository over HTTP the appropriate scheme
    would be svn+http. Likewise a Git repository on the local filesystem
    would be accessed using git+file.

    This allows us to handle the problem of multiple VCSes offering file and
    HTTP access.

    The canonical form for access using a bespoke protocol would be something
    like svn+svn. Obviously this is ugly and stupid so we accept just svn as
    an alias.
    """
    repo_type = {
        'git': GitRepo,
        'svn': SubversionRepo
    }
    url_components = urlparse(url)
    vcs, _, protocol = url_components.scheme.partition('+')
    if not protocol:
        protocol = vcs
    if vcs not in ['git', 'svn']:
        message = f"Unrecognised repository scheme: {vcs}+{protocol}"
        raise FabException(message)
    access_url = urlunparse((protocol,
                             url_components.netloc,
                             url_components.path,
                             url_components.params,
                             url_components.query,
                             url_components.fragment))
    return repo_type[vcs](access_url)
