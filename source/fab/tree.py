from collections import defaultdict
from pathlib import Path


from typing import List, Dict


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


# todo: this seems misnamed
def build_tree(program_units: List[ProgramUnit]) -> Dict[str, ProgramUnit]:
    """
    Put the list program units into a dict, keyed on name.
    """
    tree = dict()
    for p in program_units:
        tree[p.name] = p
    return tree


def extract_sub_tree(
        src_tree, key, _result=None, _missing=None, logger=None, indent=0):
    """blurb"""

    _result = _result or dict()
    _missing = _missing or set()

    if logger:
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
            src_tree, dep, _result=_result, _missing=_missing, logger=logger, indent=indent + 1)
        
    return _result, _missing




# def get_compile_order(node, tree, compile_order=None):
#     compile_order = compile_order or []
# 
#     if node.deps:
#         for dep in node.deps:
#             get_compile_order(tree[dep], tree, compile_order=compile_order)
#     else:
#         if node not in compile_order:
#             compile_order.append(node)
# 
#     return compile_order


# todo: don't leave this here
def by_type(iterable):
    result = defaultdict(set)
    for i in iterable:
        result[type(i)].add(i)
    return result
