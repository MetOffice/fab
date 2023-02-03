##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Classes and helper functions related to the dependency tree, as created by the analysis stage.

"""

# todo: we've since adopted the term "source tree", so we should probably rename this module to match.
from abc import ABC
import logging
from pathlib import Path
from typing import Set, Dict, Iterable, List, Union, Optional, Any

from fab.parse import AnalysedFile

logger = logging.getLogger(__name__)


# Todo: Better name? It's an analysed file in a dependency tree
#       (as opposed to an analysed x90 for example, which isn't part of this tree dependency analysis).
class AnalysedDependent(AnalysedFile, ABC):
    """
    An :class:`~fab.parse.AnalysedFile` which can depend on others, and be a dependency.
    Instances of this class are nodes in a source dependency tree.

    During parsing, the symbol definitions and dependencies are filled in.
    During dependency analysis, symbol dependencies are turned into file dependencies.

    """
    def __init__(self, fpath: Union[str, Path], file_hash: Optional[int] = None,
                 symbol_defs: Optional[Iterable[str]] = None, symbol_deps: Optional[Iterable[str]] = None,
                 file_deps: Optional[Iterable[Path]] = None):
        """
        :param fpath:
            The source file that was analysed.
        :param file_hash:
            The hash of the source. If omitted, Fab will evaluate lazily.
        :param symbol_defs:
            Set of symbol names defined by this source file.
        :param symbol_deps:
            Set of symbol names used by this source file.
            Can include symbols in the same file.
        :param file_deps:
            Other files on which this source depends. Must not include itself.
            This attribute is calculated during symbol analysis, after everything has been parsed.

        """
        super().__init__(fpath=fpath, file_hash=file_hash)

        self.symbol_defs: Set[str] = set(symbol_defs or {})
        self.symbol_deps: Set[str] = set(symbol_deps or {})
        self.file_deps: Set[Path] = set(file_deps or [])

        assert all([d and len(d) for d in self.symbol_defs]), "bad symbol definitions"
        assert all([d and len(d) for d in self.symbol_deps]), "bad symbol dependencies"

    def add_symbol_def(self, name):
        assert name and len(name)
        self.symbol_defs.add(name.lower())

    def add_symbol_dep(self, name):
        assert name and len(name)
        self.symbol_deps.add(name.lower())

    def add_file_dep(self, name):
        self.file_deps.add(Path(name))

    @classmethod
    def field_names(cls):
        return super().field_names() + [
            'symbol_defs',
            'symbol_deps',
            'file_deps',
        ]

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "symbol_defs": list(sorted(self.symbol_defs)),
            "symbol_deps": list(sorted(self.symbol_deps)),
            "file_deps": list(sorted(map(str, self.file_deps))),
        })
        return result

    @classmethod
    def from_dict(cls, d):
        result = cls(
            fpath=Path(d["fpath"]),
            file_hash=d["file_hash"],
            symbol_defs=set(d["symbol_defs"]),
            symbol_deps=set(d["symbol_deps"]),
            file_deps=set(map(Path, d["file_deps"])),
        )
        assert result.file_hash is not None
        return result


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


def filter_source_tree(source_tree: Dict[Path, AnalysedDependent], suffixes: Iterable[str]) -> List[AnalysedDependent]:
    """
    Pull out files with the given extensions from a source tree.

    Returns a list of :class:`~fab.dep_tree.AnalysedDependent`.

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
