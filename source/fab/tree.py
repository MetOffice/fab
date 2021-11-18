import logging
from collections import defaultdict
from pathlib import Path


logger = logging.getLogger(__name__)


# todo: might be better as a named tuple, as there's no methods
class ProgramUnit(object):
    def __init__(self, name: str, fpath: Path):
        self.name = name
        self.fpath = fpath
        self.deps = set()

    def __str__(self):
        return f"ProgramUnit {self.name} {self.fpath} {self.deps}"


class EmptyProgramUnit(object):
    def __init__(self, fpath):
        self.fpath = fpath


def extract_sub_tree(
        src_tree, key, _result=None, _missing=None, indent=0):
    """blurb"""

    _result = _result or dict()
    _missing = _missing or set()

    logger.debug("----" * indent + key)

    node = src_tree[key]
    _result[node.name] = node
    for dep in sorted(node.deps):
        if not src_tree.get(dep):
            if logger:
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
