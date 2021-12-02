import logging
from collections import defaultdict
from pathlib import Path


logger = logging.getLogger(__name__)


# todo: might be better as a named tuple, as there's no methods
class ProgramUnit(object):
    def __init__(self, name: str, fpath: Path, file_hash, deps=None):

        if deps:
            for dep in deps:
                if (not dep) or len(dep) == 0:
                    raise ValueError("Bad deps")

        self.name = name.lower()
        self.fpath = fpath
        self.hash = file_hash
        self._deps = deps or set()

    def add_dep(self, dep):
        assert dep and len(dep)
        self._deps.add(dep.lower())

    @property
    def deps(self):
        return self._deps

    def __str__(self):
        return f"ProgramUnit {self.name} {self.fpath} {self.hash} {self.deps}"

    # todo: poor name, and does it even belong in here?
    def as_dict(self):
        """Serialise"""
        return {'name': self.name, 'fpath': self.fpath, 'hash': self.hash, 'deps': ';'.join(self.deps)}

    @classmethod
    def from_dict(cls, d):
        """Deserialise"""
        return cls(name=d['name'], fpath=Path(d['fpath']), file_hash=d['hash'], deps=d['deps'].split(';'))


class EmptyProgramUnit(object):
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
def by_type(iterable):
    result = defaultdict(set)
    for i in iterable:
        result[type(i)].add(i)
    return result
