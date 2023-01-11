##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Classes and helper functions related to the dependency tree, as created by the analysis stage.

"""

# todo: we've since adopted the term "source tree", so we should probably rename this module to match.
import logging
from pathlib import Path
from typing import Set, Dict, Iterable, List

from fab.parse import AnalysedDependent
from fab.parse.c import AnalysedC
from fab.parse.fortran.fortran import AnalysedFortran

logger = logging.getLogger(__name__)


def extract_sub_tree(source_tree: Dict[Path, AnalysedDependent], root: Path, verbose=False)\
        -> Dict[Path, AnalysedDependent]:
    """
    Extract the subtree required to build the target, from the full source tree of all analysed source files.

    :param source_tree:
        The source tree of analysed files.
    :param root:
        The root of the dependency tree, this is the filename containing the Fortran program.
    :param verbose:
        Log missing dependencies.

    """
    result: Dict[Path, AnalysedDependent] = dict()
    missing: Set[Path] = set()

    _extract_sub_tree(src_tree=source_tree, key=root, dst_tree=result, missing=missing, verbose=verbose)

    if missing:
        logger.warning(f"{root} has missing deps: {missing}")

    return result


def _extract_sub_tree(src_tree: Dict[Path, AnalysedDependent], key: Path,
                      dst_tree: Dict[Path, AnalysedDependent], missing: Set[Path], verbose: bool, indent: int = 0):
    # is this node already in the sub tree?
    if key in dst_tree:
        return

    if verbose:
        logger.debug("----" * indent + str(key))

    # add it to the output tree
    node = src_tree[key]
    assert node.fpath == key, "tree corrupted"
    dst_tree[key] = node

    # add its child deps
    for file_dep in node.file_deps:

        # one of its deps is missing!
        if not src_tree.get(file_dep):
            if logger and verbose:
                logger.debug("----" * indent + " !!MISSING!! " + str(file_dep))
            missing.add(file_dep)
            continue

        # add this child dep
        _extract_sub_tree(
            src_tree=src_tree, key=file_dep, dst_tree=dst_tree, missing=missing, verbose=verbose, indent=indent + 1)


def add_mo_commented_file_deps(source_tree: Dict[Path, AnalysedDependent]):
    """
    Handle dependencies from Met Office "DEPENDS ON:" code comments which refer to a c file.
    These are the comments which refer to a .o file and not those which just refer to symbols.

    :param source_tree:
        The source tree of analysed files.

    """
    # todo: might be better to filter by type here, i.e. AnalysedFortran
    analysed_fortran: List[AnalysedFortran] = filter_source_tree(source_tree, ['.f90'])  # type: ignore
    analysed_c: List[AnalysedC] = filter_source_tree(source_tree, ['.c'])  # type: ignore

    lookup = {c.fpath.name: c for c in analysed_c}
    num_found = 0
    for f in analysed_fortran:
        num_found += len(f.mo_commented_file_deps)
        for dep in f.mo_commented_file_deps:
            f.file_deps.add(lookup[dep].fpath)
    logger.info(f"processed {num_found} DEPENDS ON file dependencies")


def filter_source_tree(source_tree: Dict[Path, AnalysedDependent], suffixes: Iterable[str])\
        -> List[AnalysedDependent]:
    """
    Pull out files with the given extensions from a source tree.

    :param source_tree:
        The source tree of analysed files.
    :param suffixes:
        The suffixes we want, including the dot.

    """
    all_files: Iterable[AnalysedDependent] = source_tree.values()
    return [af for af in all_files if af.fpath.suffix in suffixes]


def validate_dependencies(source_tree):
    """
    If any dep is missing from the tree, then it's unknown code and we won't be able to compile.

    :param source_tree:
        The source tree of analysed files.

    """
    missing = set()
    for f in source_tree.values():
        missing.update([str(file_dep) for file_dep in f.file_deps if file_dep not in source_tree])

    if missing:
        logger.error(f"Unknown dependencies, expecting build to fail: {', '.join(sorted(missing))}")
