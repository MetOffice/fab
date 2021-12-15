import logging
from collections import defaultdict
from pathlib import Path
from typing import Set, Dict, List

logger = logging.getLogger(__name__)


# FPATH = 'fpath'
# HASH = 'hash'
# SYMBOL_DEFS = 'symbol_defs'
# SYMBOL_DEPS = 'symbol_deps'
# FILE_DEPS = 'file_deps'


# todo: might be better as a named tuple, as there's no methods
class AnalysedFile(object):

    def __init__(self, fpath: Path, file_hash, symbol_deps=None, symbol_defs=None, file_deps=None, mo_commented_file_deps=None):
        self.fpath = fpath
        self.file_hash = file_hash
        self.symbol_defs: Set[str] = symbol_defs or set()
        self.symbol_deps: Set[str] = symbol_deps or set()
        self.file_deps: Set[Path] = file_deps or set()

        # dependencies from Met Office "DEPENDS ON:" code comments which refer to a c file
        self.mo_commented_file_deps: Set[str] = mo_commented_file_deps or set()

        assert all([d and len(d) for d in self.symbol_defs]), "bad symbol definitions"
        assert all([d and len(d) for d in self.symbol_deps]), "bad symbol dependencies"
        # assert all([f and len(str(f)) for f in self.file_deps]), "bad file dependencies"

    def add_symbol_def(self, name):
        assert name and len(name)
        self.symbol_defs.add(name.lower())

    def add_symbol_dep(self, name):
        assert name and len(name)
        self.symbol_deps.add(name.lower())

    def add_file_dep(self, name):
        assert name and len(name)
        self.file_deps.add(name)

    def __str__(self):
        return f"AnalysedFile {self.fpath} {self.file_hash} {self.symbol_defs} {self.symbol_deps} {self.file_deps}"

    def __eq__(self, other):
        return (
                self.fpath == other.fpath and
                self.file_hash == other.file_hash and
                self.symbol_defs == other.symbol_defs and
                self.symbol_deps == other.symbol_deps and
                self.file_deps == other.file_deps and
                self.mo_commented_file_deps == other.mo_commented_file_deps
        )

    #
    # this stuff is for reading and writing
    #

    @classmethod
    def field_names(cls):
        return ['fpath', 'file_hash', 'symbol_defs', 'symbol_deps', 'file_deps', 'mo_commented_file_deps']

    # todo: poor name, and does it even belong in here?
    def as_dict(self):
        """Serialise"""
        return {
            "fpath": self.fpath,
            "file_hash": self.file_hash,
            "symbol_deps": ';'.join(self.symbol_deps),
            "symbol_defs": ';'.join(self.symbol_defs),
            "file_deps": ';'.join(map(str, self.file_deps)),
            "mo_commented_file_deps": ';'.join(self.mo_commented_file_deps),
        }

    @classmethod
    def from_dict(cls, d):
        """Deserialise"""
        return cls(
            fpath=Path(d["fpath"]),
            file_hash=int(d["file_hash"]),
            symbol_deps=d["symbol_deps"].split(';') if d["symbol_deps"] else [],
            symbol_defs=d["symbol_defs"].split(';') if d["symbol_defs"] else [],
            file_deps=map(Path, d["file_deps"].split(';')) if d["file_deps"] else [],
            mo_commented_file_deps=d["mo_commented_file_deps"].split(';') if d["mo_commented_file_deps"] else [],
        )


class EmptySourceFile(object):
    def __init__(self, fpath):
        self.fpath = fpath


def extract_sub_tree(
        src_tree: Dict[Path, AnalysedFile], key: Path, _result=None, _missing=None, indent=0, verbose=False):
    """
    Extract a sub tree from a tree.

    Extracts a dict of program units, required to build the target,
    from the full dict of all program units.

    todo: better docstring
    """

    _result = _result or dict()
    _missing = _missing or set()

    # is this node already in the target tree?
    if key in _result:
        return

    if verbose:
        logger.debug("----" * indent + str(key))

    # find the root of the subtree
    node = src_tree[key]
    assert node.fpath == key

    # add it to the output tree
    _result[key] = node

    # add its child deps
    for file_dep in node.file_deps:

        # one of its deps is missing!
        if not src_tree.get(file_dep):
            if logger and verbose:
                logger.debug("----" * indent + "!!!!" + str(file_dep))
            _missing.add(file_dep)
            continue

        # add this child dep
        extract_sub_tree(
            src_tree, file_dep, _result=_result, _missing=_missing, indent=indent + 1)
        
    return _result, _missing


# todo: don't leave this here
# TODO: This doesn't work with exceptions very well, yet
# todo: nasty surprise when sending in a list?
def by_type(iterable):
    result = defaultdict(set)
    for i in iterable:
        result[type(i)].add(i)
    return result


def mo_commented_file_deps(analysed_fortran: List[AnalysedFile], analysed_c: List[AnalysedFile]):
    """
    Handle dependencies from Met Office "DEPENDS ON:" code comments which refer to a c file.
    """
    lookup = {c.fpath.name: c for c in analysed_c}
    for f in analysed_fortran:
        for dep in f.mo_commented_file_deps:
            f.file_deps.add(lookup[dep])
