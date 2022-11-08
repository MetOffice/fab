##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Classes and helper functions related to the dependency tree, as created by the analysis stage.

"""

# todo: we've since adopted the term "source tree", so we should probably rename this module to match.
import json
import logging
from pathlib import Path
from typing import Set, Dict, Iterable, Union, Any, Optional

from fab.util import file_checksum

logger = logging.getLogger(__name__)


# todo: this might be better placed in the analyse step
class AnalysedFile(object):
    """
    An analysis result for a single file, containing module and symbol definitions and dependencies.

    The user unlikely to encounter this class unless they need to provide a workaround for an fparser issue.
    In this case they can omit the file hash and Fab will lazily evaluate it.
    However, with this lazy evaluation, the object cannot be put into a set or otherwise hashed
    until the target file exists, which might not happen until later in the build.

    """
    def __init__(self, fpath: Union[str, Path], file_hash: Optional[int] = None,
                 module_defs: Optional[Iterable[str]] = None, symbol_defs: Optional[Iterable[str]] = None,
                 module_deps: Optional[Iterable[str]] = None, symbol_deps: Optional[Iterable[str]] = None,
                 file_deps: Optional[Iterable[Path]] = None, mo_commented_file_deps: Optional[Iterable[str]] = None):
        """
        :param fpath:
            The source file that was analysed.
        :param file_hash:
            The hash of the source. The user is encouraged not to provide this, as Fab can do it for them.
        :param module_defs:
            Set of module names defined by this source file.
            A subset of symbol_defs
        :param symbol_defs:
            Set of symbol names defined by this source file.
        :param symbol_deps:
            Set of symbol names used by this source file.
            Can include symbols in the same file.
        :param file_deps:
            Other files on which this source depends. Must not include itself.
        :param mo_commented_file_deps:
            A set of C file names, without paths, on which this file depends.
            Comes from "DEPENDS ON:" comments which end in ".o".

        """
        self.fpath = Path(fpath)
        # the self.file_hash property (no underscore) has lazy evaluation; the file might not exist yet.
        self._file_hash: Optional[int] = file_hash
        self.module_defs: Set[str] = set(module_defs or {})
        self.symbol_defs: Set[str] = set(symbol_defs or {})
        self.module_deps: Set[str] = set(module_deps or {})
        self.symbol_deps: Set[str] = set(symbol_deps or {})
        self.file_deps: Set[Path] = set(file_deps or {})

        # dependencies from Met Office "DEPENDS ON:" code comments which refer to a c file
        self.mo_commented_file_deps: Set[str] = set(mo_commented_file_deps or [])

        assert all([d and len(d) for d in self.module_defs]), "bad module definitions"
        assert all([d and len(d) for d in self.symbol_defs]), "bad symbol definitions"
        assert all([d and len(d) for d in self.module_deps]), "bad module dependencies"
        assert all([d and len(d) for d in self.symbol_deps]), "bad symbol dependencies"

        # todo: this feels a little clanky. We could just maintain separate lists of modules and other symbols,
        #   but that feels more clanky.
        assert self.module_defs <= self.symbol_defs, "modules definitions must also be symbol definitions"
        assert self.module_deps <= self.symbol_deps, "modules dependencies must also be symbol dependencies"

    @property
    def file_hash(self):
        # If we haven't provided a file hash, we can't be hashed (i.e. put into a set) until the target file exists.
        # This only affects user workarounds of fparser issues when the user has not provided a file hash.
        if self._file_hash is None:
            if not self.fpath.exists():
                raise ValueError(f"analysed file '{self.fpath}' does not exist")
            self._file_hash: int = file_checksum(self.fpath).file_hash
        return self._file_hash

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
        return hash((
            self.fpath,
            self.file_hash,
            tuple(sorted(self.module_defs)),
            tuple(sorted(self.symbol_defs)),
            tuple(sorted(self.module_deps)),
            tuple(sorted(self.symbol_deps)),
            tuple(sorted(self.file_deps)),
            tuple(sorted(self.mo_commented_file_deps)),
        ))

    def save(self, fpath: Union[str, Path]):
        d = self.to_dict()
        json.dump(d, open(fpath, 'wt'), indent=4)

    @classmethod
    def load(cls, fpath: Union[str, Path]):
        d = json.load(open(fpath))
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


# Possibly overkill to have a class for this, but it makes analysis code simpler via type filtering.
class EmptySourceFile(object):
    """
    An analysis result for a file which resulted in an empty parse tree.

    """
    def __init__(self, fpath: Path):
        self.fpath = fpath


def extract_sub_tree(source_tree: Dict[Path, AnalysedFile], root: Path, verbose=False) -> Dict[Path, AnalysedFile]:
    """
    Extract the subtree required to build the target, from the full source tree of all analysed source files.

    :param source_tree:
        The source tree of analysed files.
    :param root:
        The root of the dependency tree, this is the filename containing the Fortran program.
    :param verbose:
        Log missing dependencies.

    """
    result: Dict[Path, AnalysedFile] = dict()
    missing: Set[Path] = set()

    _extract_sub_tree(src_tree=source_tree, key=root, dst_tree=result, missing=missing, verbose=verbose)

    if missing:
        logger.warning(f"{root} has missing deps: {missing}")

    return result


def _extract_sub_tree(src_tree: Dict[Path, AnalysedFile], key: Path,
                      dst_tree: Dict[Path, AnalysedFile], missing: Set[Path], verbose: bool, indent: int = 0):
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


def add_mo_commented_file_deps(source_tree: Dict[Path, AnalysedFile]):
    """
    Handle dependencies from Met Office "DEPENDS ON:" code comments which refer to a c file.
    These are the comments which refer to a .o file and not those which just refer to symbols.

    :param source_tree:
        The source tree of analysed files.

    """
    analysed_fortran = filter_source_tree(source_tree, '.f90')
    analysed_c = filter_source_tree(source_tree, '.c')

    lookup = {c.fpath.name: c for c in analysed_c}
    num_found = 0
    for f in analysed_fortran:
        num_found += len(f.mo_commented_file_deps)
        for dep in f.mo_commented_file_deps:
            f.file_deps.add(lookup[dep].fpath)
    logger.info(f"processed {num_found} DEPENDS ON file dependencies")


def filter_source_tree(source_tree: Dict[Path, AnalysedFile], suffixes: Iterable[str]):
    """
    Pull out files with the given extensions from a source tree.

    Returns a list of :class:`~fab.dep_tree.AnalysedFile`.

    :param source_tree:
        The source tree of analysed files.
    :param suffixes:
        The suffixes we want, including the dot.

    """
    all_files: Iterable[AnalysedFile] = source_tree.values()
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
