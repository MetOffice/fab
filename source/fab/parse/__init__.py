# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import json
import logging
from abc import ABC
from pathlib import Path
from typing import Union, Optional, Iterable, Set, Dict, Any

from fab.util import file_checksum


logger = logging.getLogger(__name__)


class ParseException(Exception):
    pass


class AnalysedFileBase(ABC):
    """
    Analysis results for a single file.

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


# todo: there's a design weakness relating to this class:
#       we don't save empty results which means we'll keep reanalysing them
class EmptySourceFile(AnalysedFileBase):
    """
    An analysis result for a file which resulted in an empty parse tree.

    """
    def __init__(self, fpath: Union[str, Path]):
        """
        :param fpath:
            The path of the file which was analysed.

        """
        super().__init__(fpath=fpath)


class AnalysedX90(AnalysedFileBase):
    """
    Analysis results for an x90 file.

    """
    def __init__(self, fpath: Union[str, Path], file_hash: int, kernel_deps: Iterable[str]):
        """
        :param fpath:
            The path of the x90 file.
        :param file_hash:
            The checksum of the x90 file.
        :param kernel_deps:
            Kernel symbols used by the x90 file.

        """
        super().__init__(fpath=fpath, file_hash=file_hash)
        self.kernel_deps: Set[str] = set(kernel_deps)


class AnalysedFortran(AnalysedFileBase):
    """
    An analysis result for a single file, containing module and symbol definitions and dependencies.

    The user should be unlikely to encounter this class. When a language parser is unable to process a source file,
    a :class:`~fab.dep_tree.ParserWorkaround` object can be provided to the :class:`~fab.steps.analyse.Analyse` step,
    which will be converted at runtime into an `AnalysedFile` object.

    """
    def __init__(self, fpath: Union[str, Path], file_hash: Optional[int] = None,
                 module_defs: Optional[Iterable[str]] = None, symbol_defs: Optional[Iterable[str]] = None,
                 module_deps: Optional[Iterable[str]] = None, symbol_deps: Optional[Iterable[str]] = None,
                 mo_commented_file_deps: Optional[Iterable[str]] = None, file_deps: Optional[Iterable[Path]] = None):
        """
        :param fpath:
            The source file that was analysed.
        :param file_hash:
            The hash of the source. If omitted, Fab will evaluate lazily.
        :param module_defs:
            Set of module names defined by this source file.
            A subset of symbol_defs
        :param symbol_defs:
            Set of symbol names defined by this source file.
        :param module_deps:
            Set of module names used by this source file.
        :param symbol_deps:
            Set of symbol names used by this source file.
            Can include symbols in the same file.
        :param mo_commented_file_deps:
            A set of C file names, without paths, on which this file depends.
            Comes from "DEPENDS ON:" comments which end in ".o".
        :param file_deps:
            Other files on which this source depends. Must not include itself.
            This attribute is calculated during symbol analysis, after everything has been parsed.

        """
        super().__init__(fpath=fpath, file_hash=file_hash)

        self.module_defs: Set[str] = set(module_defs or {})
        self.symbol_defs: Set[str] = set(symbol_defs or {})
        self.module_deps: Set[str] = set(module_deps or {})
        self.symbol_deps: Set[str] = set(symbol_deps or {})
        self.mo_commented_file_deps: Set[str] = set(mo_commented_file_deps or [])
        self.file_deps: Set[Path] = set(file_deps or {})

        assert all([d and len(d) for d in self.module_defs]), "bad module definitions"
        assert all([d and len(d) for d in self.symbol_defs]), "bad symbol definitions"
        assert all([d and len(d) for d in self.module_deps]), "bad module dependencies"
        assert all([d and len(d) for d in self.symbol_deps]), "bad symbol dependencies"

        # todo: this feels a little clanky.
        assert self.module_defs <= self.symbol_defs, "modules definitions must also be symbol definitions"
        assert self.module_deps <= self.symbol_deps, "modules dependencies must also be symbol dependencies"

    def add_module_def(self, name):
        self.module_defs.add(name.lower())
        self.add_symbol_def(name)

    def add_symbol_def(self, name):
        assert name and len(name)
        self.symbol_defs.add(name.lower())

    def add_module_dep(self, name):
        self.module_deps.add(name.lower())
        self.add_symbol_dep(name)

    def add_symbol_dep(self, name):
        assert name and len(name)
        self.symbol_deps.add(name.lower())

    def add_file_dep(self, name):
        assert name and len(name)
        self.file_deps.add(name)

    @property
    def mod_filenames(self):
        """The mod_filenames property defines which module files are expected to be created (but not where)."""
        return {f'{mod}.mod' for mod in self.module_defs}

    @classmethod
    def field_names(cls):
        """Defines the order in which we want fields to appear if a human is reading them"""
        return [
            'fpath', 'file_hash',
            'module_defs', 'symbol_defs',
            'module_deps', 'symbol_deps',
            'file_deps', 'mo_commented_file_deps',
        ]

    def __str__(self):
        values = [getattr(self, field_name) for field_name in self.field_names()]
        return 'AnalysedFile ' + ' '.join(map(str, values))

    def __repr__(self):
        params = ', '.join([f'{f}={getattr(self, f)}' for f in self.field_names()])
        return f'AnalysedFile({params})'

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __hash__(self):
        # If we haven't been given a file hash, we can't be hashed (i.e. put into a set) until the target file exists.
        # This only affects user workarounds of fparser issues when the user has not provided a file hash.
        return hash((
            self.fpath,
            self.file_hash,  # this is a lazily evaluated property
            tuple(sorted(self.module_defs)),
            tuple(sorted(self.symbol_defs)),
            tuple(sorted(self.module_deps)),
            tuple(sorted(self.symbol_deps)),
            tuple(sorted(self.file_deps)),
            tuple(sorted(self.mo_commented_file_deps)),
        ))

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
        return {
            "fpath": str(self.fpath),
            "file_hash": self.file_hash,
            "module_defs": list(self.module_defs),
            "symbol_defs": list(self.symbol_defs),
            "module_deps": list(self.module_deps),
            "symbol_deps": list(self.symbol_deps),
            "file_deps": list(map(str, self.file_deps)),
            "mo_commented_file_deps": list(self.mo_commented_file_deps),
        }

    @classmethod
    def from_dict(cls, d):
        result = cls(
            fpath=Path(d["fpath"]),
            file_hash=d["file_hash"],
            module_defs=set(d["module_defs"]),
            symbol_defs=set(d["symbol_defs"]),
            module_deps=set(d["module_deps"]),
            symbol_deps=set(d["symbol_deps"]),
            file_deps=set(map(Path, d["file_deps"])),
            mo_commented_file_deps=set(d["mo_commented_file_deps"]),
        )
        assert result.file_hash is not None
        return result


class FortranParserWorkaround(object):
    """
    Use this class to create a workaround when the Fortran parser is unable to process a valid source file.

    You must manually examine the source file and list:
     - module definitions
     - module dependencies
     - symbols defined outside a module
     - symbols used without a use statement

    Params are as for :class:`~fab.dep_tree.AnalysedFortranBase`.

    This class is intended to be passed to the :class:`~fab.steps.analyse.Analyse` step.

    """
    def __init__(self, fpath: Union[str, Path],
                 module_defs: Optional[Iterable[str]] = None, symbol_defs: Optional[Iterable[str]] = None,
                 module_deps: Optional[Iterable[str]] = None, symbol_deps: Optional[Iterable[str]] = None,
                 mo_commented_file_deps: Optional[Iterable[str]] = None):
        """
        :param fpath:
            The source file that was analysed.
        :param module_defs:
            Set of module names defined by this source file.
            A subset of symbol_defs
        :param symbol_defs:
            Set of symbol names defined by this source file.
        :param module_deps:
            Set of module names used by this source file.
        :param symbol_deps:
            Set of symbol names used by this source file.
            Can include symbols in the same file.
        :param mo_commented_file_deps:
            A set of C file names, without paths, on which this file depends.
            Comes from "DEPENDS ON:" comments which end in ".o".

        """
        super().__init__(fpath=fpath)
        self.module_defs: Set[str] = set(module_defs or {})
        self.symbol_defs: Set[str] = set(symbol_defs or {})
        self.module_deps: Set[str] = set(module_deps or {})
        self.symbol_deps: Set[str] = set(symbol_deps or {})
        self.mo_commented_file_deps: Set[str] = set(mo_commented_file_deps or [])

    def as_analysed_file(self):

        # To be as helpful as possible, we allow the user to omit module defs/deps from the symbol defs/deps.
        # However, they need to be there so do this now.
        self.symbol_defs = self.symbol_defs | self.module_defs
        self.symbol_deps = self.symbol_deps | self.module_deps

        return AnalysedFortran(
            fpath=self.fpath, file_hash=file_checksum(self.fpath).file_hash,
            module_defs=self.module_defs, symbol_defs=self.symbol_defs,
            module_deps=self.module_deps, symbol_deps=self.symbol_deps,
            mo_commented_file_deps=self.mo_commented_file_deps,
        )
