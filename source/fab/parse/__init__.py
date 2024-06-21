# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import json
import logging
from abc import ABC
from pathlib import Path
from typing import Union, Optional, Dict, Any, Set

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

        """
        self.fpath = Path(fpath)
        self._file_hash = file_hash

    @property
    def file_hash(self) -> int:
        if self._file_hash is None:
            if not self.fpath.exists():
                raise ValueError(f"analysed file '{self.fpath}' does not exist")
            self._file_hash = file_checksum(self.fpath).file_hash
        return self._file_hash

    def __eq__(self, other):
        # todo: better to use self.field_names() instead of vars(self) in order to evaluate any lazy attributes?
        return vars(self) == vars(other)

    # persistence
    def to_dict(self) -> Dict[str, Any]:
        """
        Create a dict representing the object.

        The dict may be written to json, so can't contain sets.
        Lists are sorted for reproducibility in testing.

        """
        return {
            "fpath": str(self.fpath),
            "file_hash": self.file_hash
        }

    @classmethod
    def from_dict(cls, d):
        raise NotImplementedError

    def save(self, fpath: Union[str, Path]):
        # subclasses don't need to override this method
        d = self.to_dict()
        d["cls"] = self.__class__.__name__
        json.dump(d, open(fpath, 'wt'), indent=4)

    @classmethod
    def load(cls, fpath: Union[str, Path]):
        # subclasses don't need to override this method
        d = json.load(open(fpath))
        found_class = d["cls"]
        if found_class != cls.__name__:
            raise ValueError(f"Expected class name '{cls.__name__}', found '{found_class}'")
        return cls.from_dict(d)

    # human readability
    @classmethod
    def field_names(cls):
        """
        Defines the order in which we want fields to appear in str or repr strings.

        Calling this helps to ensure any lazy attributes are evaluated before use,
        e.g when constructing a string representation of the instance, or generating a hash value.

        """
        return ['fpath', 'file_hash']

    def __str__(self):
        # We use self.field_names() instead of vars(self) in order to evaluate any lazy attributes.
        values = [getattr(self, field_name) for field_name in self.field_names()]
        return f'{self.__class__.__name__} ' + ' '.join(map(str, values))

    def __repr__(self):
        params = ', '.join([f'{f}={repr(getattr(self, f))}' for f in self.field_names()])
        return f'{self.__class__.__name__}({params})'

    # We need to be hashable before we can go into a set, which is useful for our subclasses.
    # Note, the numerical result will change with each Python invocation.
    def __hash__(self):
        # Build up a list of things to hash, from our attributes.
        # We use self.field_names() rather than vars(self) because we want to evaluate any lazy attributes.
        # We turn dicts and sets into sorted tuples for hashing.
        # todo: There's a good reason dicts and sets aren't supposed to be hashable.
        #       Please see https://github.com/metomi/fab/issues/229
        things = set()
        for field_name in self.field_names():
            thing = getattr(self, field_name)
            if isinstance(thing, Dict):
                things.add(tuple(sorted(thing.items())))
            elif isinstance(thing, Set):
                things.add(tuple(sorted(thing)))
            else:
                things.add(thing)

        return hash(tuple(things))


# todo: There's a design weakness relating to this class:
#       we don't save empty results, which means we'll keep reanalysing them.
#       We should save empty files and allow the loading to detect this, as it already reads the class name.
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

    @classmethod
    def from_dict(cls, d):
        # todo: load & save should be implemented here and used by the calling code, to save reanalysis.
        raise NotImplementedError
