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
from subprocess import PIPE, run, Popen
import tarfile
from typing import Optional
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


class GitRepo(Repository):
    """
    Extracts a source tree from a Git repository.

    This class currently wraps the Git command-line client but that may prove
    unsatisfactory. In particular it could be too slow. In that case we should
    examine the possibility of using Python bindings.
    """
    _TIMEOUT = 4  # seconds

    def __init__(self, url: str):
        super().__init__(url)

    def extract(self, target: Path):
        target.parent.mkdir(parents=True, exist_ok=True)
        command = ['git', 'archive',
                   '--format', 'tar',
                   '--remote', self.url,
                   'HEAD']
        process = Popen(command, stdout=PIPE, stderr=PIPE)

        extract_message: Optional[str] = None
        try:
            extractor = tarfile.open(fileobj=process.stdout, mode='r|')
            extractor.extractall(target)
        except Exception as ex:
            extract_message = "Problem extracting archived repository: "
            extract_message += str(ex)
            process.kill()

        process.wait(self._TIMEOUT)
        if process.returncode != 0:
            message = "Fault exporting tree from Git repository:"
            if process.stderr:
                error = [line.decode('utf-8')
                         for line in process.stderr.readlines()]
                message += '\n' + '\n'.join(error)
            if extract_message:
                message += '\n' + extract_message
            raise FabException(message)


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

    Our approach here may not be standard but it is common practice.

    We have adopted a URL scheme form of <repo>+<protocol>. Thus a
    Subversion repository accessed over HTTP would be svn+http://.

    We also support a shorthand to match normal usage so svn:// is
    considered an alias for svn+svn://.
    """
    repo_type = {
        'git': GitRepo,
        'svn': SubversionRepo
    }

    url_components = urlparse(url)
    repo, _, protocol = url_components.scheme.partition('+')
    if not protocol:
        protocol = repo

    if repo not in repo_type.keys():
        message = f"Unrecognised repository scheme: {repo}+{protocol}"
        raise FabException(message)

    access_url = urlunparse((protocol,
                             url_components.netloc,
                             url_components.path,
                             url_components.params,
                             url_components.query,
                             url_components.fragment))
    return repo_type[repo](access_url)
