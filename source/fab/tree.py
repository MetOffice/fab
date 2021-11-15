from collections import defaultdict
from pathlib import Path


# todo: might be better as a named tuple, if there's no methods
from typing import List


class ProgramUnit(object):
    """A program unit in a file with dependencies"""
    def __init__(self, name: str, fpath: Path):
        self.name = name
        self.fpath = fpath
        self.deps = set()


def build_tree(program_units: List[ProgramUnit]):
    """
    Put the list program units into a dict, keyed on name.
    """
    tree = dict()
    for p in program_units:
        tree[p.name] = p
    return tree


# def walk_tree(node, all_nodes, compile_order=None):
#     compile_order = compile_order or []
#     if node.deps:
#         for dep in node.deps:
#             walk_tree(dep, compile_order)
#     else:
#         if node not in compile_order:
#             compile_order.append(node)
#     return compile_order


# todo: don't leave this here
def by_type(iterable):
    result = defaultdict(set)
    for i in iterable:
        result[type(i)].add(i)
    return result
