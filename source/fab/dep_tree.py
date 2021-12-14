import logging
from collections import defaultdict
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)


FPATH = 'fpath'
HASH = 'hash'
SYMBOL_DEFS = 'symbol_defs'
SYMBOL_DEPS = 'symbol_deps'
FILE_DEPS = 'file_deps'


# todo: might be better as a named tuple, as there's no methods
class AnalysedFile(object):

    def __init__(self, fpath: Path, file_hash, symbol_deps=None, symbol_defs=None, file_deps=None):
        self.fpath = fpath
        self.hash = file_hash
        self.symbol_defs: Set[str] = symbol_defs or set()
        self.symbol_deps: Set[str] = symbol_deps or set()
        self.file_deps: Set[Path] = file_deps or set()

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
        return f"ProgramUnit {self.fpath} {self.hash} {self.symbol_defs} {self.symbol_deps} {self.file_deps}"

    def __eq__(self, other):
        return (
            self.fpath == other.fpath and
            self.hash == other.hash and
            self.symbol_defs == other.symbol_defs and
            self.symbol_deps == other.symbol_deps and
            self.file_deps == other.file_deps
        )

    # todo: poor name, and does it even belong in here?
    def as_dict(self):
        """Serialise"""
        return {
            FPATH: self.fpath,
            HASH: self.hash,
            SYMBOL_DEPS: ';'.join(self.symbol_deps),
            SYMBOL_DEFS: ';'.join(self.symbol_defs),
        }

    @classmethod
    def from_dict(cls, d):
        """Deserialise"""
        return cls(
            fpath=Path(d[FPATH]),
            file_hash=d[HASH],
            symbol_deps=d[SYMBOL_DEPS].split(';'),
            symbol_defs=d[SYMBOL_DEFS].split(';'),
        )


class EmptySourceFile(object):
    def __init__(self, fpath):
        self.fpath = fpath


def extract_sub_tree(
        src_tree, key, _result=None, _missing=None, indent=0, verbose=False):
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
        logger.debug("----" * indent + key)

    node = src_tree[key]
    assert node.name == key
    _result[key] = node
    for dep in sorted(node.deps):  # sorted for readability
        if not src_tree.get(dep):
            if logger and verbose:
                logger.debug("----" * indent + "!!!!" + dep)
            _missing.add(dep)
            continue
        extract_sub_tree(
            src_tree, dep, _result=_result, _missing=_missing, indent=indent + 1)
        
    return _result, _missing


# todo: don't leave this here
# TODO: This doesn't work with exceptions very well, yet
def by_type(iterable):
    result = defaultdict(set)
    for i in iterable:
        result[type(i)].add(i)
    return result
