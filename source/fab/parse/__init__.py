# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import json
import logging
from abc import ABC
from pathlib import Path
from typing import Union, Optional, Dict, Any

from fab.util import file_checksum


logger = logging.getLogger(__name__)


class ParseException(Exception):
    pass


class AnalysedFile(ABC):
    """
    Analysis results for a single file. Abstract base class.

    """
    def __init__(self, fpath: Union[str, Path], file_hash: Optional[int] = None):
        """
        :param fpath:
            The path of the file which was analysed.
        :param file_hash:
            The checksum of the file which was analysed.
            If omitted, Fab will evaluate lazily.

        If not provided, the `self.file_hash` property is lazily evaluated in case the file does not yet exist.
        This can happen when defining a parser workaround for a file which is created at runtime.

        """
        self.fpath = Path(fpath)
        self._file_hash = file_hash

    @property
    def file_hash(self):
        if self._file_hash is None:
            if not self.fpath.exists():
                raise ValueError(f"analysed file '{self.fpath}' does not exist")
            self._file_hash: int = file_checksum(self.fpath).file_hash
        return self._file_hash

    def save(self, fpath: Union[str, Path]):
        d = self.to_dict()
        d["cls"] = self.__class__.__name__
        json.dump(d, open(fpath, 'wt'), indent=4)

    @classmethod
    def load(cls, fpath: Union[str, Path]):
        d = json.load(open(fpath))
        found_class = d["cls"]
        if found_class != cls.__name__:
            logger.error(f"Expected class name '{cls.__name__}', got '{found_class}'")
            return None
        return cls.from_dict(d)

    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, d):
        raise NotImplementedError


# todo: there's a design weakness relating to this class:
#       we don't save empty results which means we'll keep reanalysing them
class EmptySourceFile(AnalysedFile):
    """
    An analysis result for a file which resulted in an empty parse tree.

    """
    def __init__(self, fpath: Union[str, Path]):
        """
        :param fpath:
            The path of the file which was analysed.

        """
        super().__init__(fpath=fpath)
