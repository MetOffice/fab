# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Fortran language handling classes.

"""
import logging
from pathlib import Path
from typing import Union, Optional, Iterable, Dict, Any, Set

from fparser.two.Fortran2003 import (  # type: ignore
    Entity_Decl_List, Use_Stmt, Module_Stmt, Program_Stmt, Subroutine_Stmt, Function_Stmt, Language_Binding_Spec,
    Char_Literal_Constant, Interface_Block, Name, Comment, Module, Call_Stmt, Derived_Type_Def, Derived_Type_Stmt,
    Type_Attr_Spec_List, Type_Attr_Spec, Type_Name)

# todo: what else should we be importing from 2008 instead of 2003? This seems fragile.
from fparser.two.Fortran2008 import (  # type: ignore
    Type_Declaration_Stmt, Attr_Spec_List)

from fab.dep_tree import AnalysedDependent
from fab.parse.fortran_common import iter_content, _has_ancestor_type, _typed_child, FortranAnalyserBase
from fab.util import file_checksum, string_checksum

logger = logging.getLogger(__name__)


class AnalysedFortran(AnalysedDependent):
    """
    An analysis result for a single file, containing module and symbol definitions and dependencies.

    The user should be unlikely to encounter this class. If the third-party fortran parser is unable to process
    a source file, a :class:`~fab.dep_tree.FortranParserWorkaround` object can be provided to the
    :class:`~fab.steps.analyse.Analyse` step, which will be converted at runtime into an instance of this class.

    """
    def __init__(self, fpath: Union[str, Path], file_hash: Optional[int] = None,
                 program_defs: Optional[Iterable[str]] = None,
                 module_defs: Optional[Iterable[str]] = None, symbol_defs: Optional[Iterable[str]] = None,
                 module_deps: Optional[Iterable[str]] = None, symbol_deps: Optional[Iterable[str]] = None,
                 mo_commented_file_deps: Optional[Iterable[str]] = None, file_deps: Optional[Iterable[Path]] = None,
                 psyclone_kernels: Optional[Dict[str, int]] = None):
        """
        :param fpath:
            The source file that was analysed.
        :param file_hash:
            The hash of the source. If omitted, Fab will evaluate lazily.
        :param program_defs:
            Set of program names defined by this source file.
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
        :param psyclone_kernels:
            The hash of any PSyclone kernel metadata found in this source file, by name.

        """
        super().__init__(fpath=fpath, file_hash=file_hash,
                         symbol_defs=symbol_defs, symbol_deps=symbol_deps, file_deps=file_deps)

        self.program_defs: Set[str] = set(program_defs or [])
        self.module_defs: Set[str] = set(module_defs or [])
        self.module_deps: Set[str] = set(module_deps or [])
        self.mo_commented_file_deps: Set[str] = set(mo_commented_file_deps or [])

        # Todo: Ideally Psyclone stuff would not be part of this general fortran analysis code.
        #       Instead, perhaps we could inject bespoke node handling into the fortran analyser.
        self.psyclone_kernels: Dict[str, int] = psyclone_kernels or {}

        self.validate()

    def add_program_def(self, name):
        self.program_defs.add(name.lower())
        self.add_symbol_def(name)

    def add_module_def(self, name):
        self.module_defs.add(name.lower())
        self.add_symbol_def(name)

    def add_module_dep(self, name):
        self.module_deps.add(name.lower())
        self.add_symbol_dep(name)

    @property
    def mod_filenames(self):
        """The mod_filenames property defines which module files are expected to be created (but not where)."""
        return {f'{mod}.mod' for mod in self.module_defs}

    @classmethod
    def field_names(cls):
        # we're not using the super class because we want to insert, not append the order of our attributes
        return [
            'fpath', 'file_hash',
            'program_defs',
            'module_defs', 'symbol_defs',
            'module_deps', 'symbol_deps',
            'mo_commented_file_deps',
            'file_deps',
            'psyclone_kernels',
        ]

    def to_dict(self) -> Dict[str, Any]:
        # These dicts will be written to json files, so can't contain sets.
        # We sort the lists for reproducibility in testing.
        result = super().to_dict()
        result.update({
            "program_defs": list(sorted(self.program_defs)),
            "module_defs": list(sorted(self.module_defs)),
            "module_deps": list(sorted(self.module_deps)),
            "mo_commented_file_deps": list(sorted(self.mo_commented_file_deps)),
            "psyclone_kernels": self.psyclone_kernels,
        })

        return result

    @classmethod
    def from_dict(cls, d):
        result = cls(
            fpath=Path(d["fpath"]),
            file_hash=d["file_hash"],
            program_defs=set(d["program_defs"]),
            module_defs=set(d["module_defs"]),
            symbol_defs=set(d["symbol_defs"]),
            module_deps=set(d["module_deps"]),
            symbol_deps=set(d["symbol_deps"]),
            file_deps=set(map(Path, d["file_deps"])),
            mo_commented_file_deps=set(d["mo_commented_file_deps"]),
            psyclone_kernels=d["psyclone_kernels"],
        )

        result.validate()
        return result

    def validate(self):
        assert self.file_hash is not None

        assert all([d and len(d) for d in self.program_defs]), "bad program definitions"
        assert all([d and len(d) for d in self.module_defs]), "bad module definitions"
        assert all([d and len(d) for d in self.symbol_defs]), "bad symbol definitions"
        assert all([d and len(d) for d in self.module_deps]), "bad module dependencies"
        assert all([d and len(d) for d in self.symbol_deps]), "bad symbol dependencies"

        # todo: this feels a little clanky.
        assert self.program_defs <= self.symbol_defs, "programs definitions must also be symbol definitions"
        assert self.module_defs <= self.symbol_defs, "modules definitions must also be symbol definitions"
        assert self.module_deps <= self.symbol_deps, "modules dependencies must also be symbol dependencies"


# todo: consider, this doesn't really need to be a class at all...it could just be a function...
class FortranAnalyser(FortranAnalyserBase):
    """
    A build step which analyses a fortran file using fparser2, creating an :class:`~fab.dep_tree.AnalysedFortran`.

    """
    def __init__(self, std=None, ignore_mod_deps: Optional[Iterable[str]] = None):
        """
        :param std:
            The Fortran standard.
        :param ignore_mod_deps:
            Module names to ignore in use statements.

        """
        super().__init__(result_class=AnalysedFortran, std=std)
        self.ignore_mod_deps: Iterable[str] = list(ignore_mod_deps or [])
        self.depends_on_comment_found = False

    def walk_nodes(self, fpath, file_hash, node_tree) -> AnalysedFortran:

        # see what's in the tree
        analysed_fortran = AnalysedFortran(fpath=fpath, file_hash=file_hash)
        for obj in iter_content(node_tree):
            obj_type = type(obj)
            try:

                # todo: ?replace these with function lookup dict[type, func]? - Or the new match statement, Python 3.10
                if obj_type == Use_Stmt:
                    self._process_use_statement(analysed_fortran, obj)  # raises

                elif obj_type == Call_Stmt:
                    called_name = _typed_child(obj, Name)
                    # called_name will be None for calls like thing%method(),
                    # which is fine as it doesn't reveal a dependency on an external function.
                    if called_name:
                        analysed_fortran.add_symbol_dep(called_name.string)

                elif obj_type == Program_Stmt:
                    analysed_fortran.add_program_def(str(obj.get_name()))

                elif obj_type == Module_Stmt:
                    analysed_fortran.add_module_def(str(obj.get_name()))

                elif obj_type in (Subroutine_Stmt, Function_Stmt):
                    self._process_subroutine_or_function(analysed_fortran, fpath, obj)

                # variables with c binding are found inside a Type_Declaration_Stmt.
                # todo: This was used for exporting a Fortran variable for use in C.
                #       Variable bindings are bidirectional - does this work the other way round, too?
                #       Make sure we have a test for it.
                elif obj_type == Type_Declaration_Stmt:
                    # bound?
                    specs = _typed_child(obj, Attr_Spec_List)
                    if specs and _typed_child(specs, Language_Binding_Spec):
                        self._process_variable_binding(analysed_fortran, obj)

                elif obj_type == Comment:
                    self._process_comment(analysed_fortran, obj)

                # Record any psyclone kernel metadata (type definitions) we find.
                # todo: how can we separate this psyclone concern out elegantly, for loose coupling?
                elif obj_type == Derived_Type_Def:
                    try:
                        stmt = _typed_child(obj, Derived_Type_Stmt)
                        spec_list = _typed_child(stmt, Type_Attr_Spec_List)
                        type_spec = _typed_child(spec_list, Type_Attr_Spec)
                        if type_spec.children[0] == 'EXTENDS':
                            if (
                                    isinstance(type_spec.children[1], Name)
                                    and type_spec.children[1].string == 'kernel_type'
                            ):

                                # We've found a psyclone kernel metadata. What's it called?
                                kernel_name = _typed_child(stmt, Type_Name).string

                                # Hash this kernel metadata.
                                # If it changes, Psyclone will reprocess any x90 which uses it.
                                kernel_hash = string_checksum(str(obj))

                                assert kernel_name not in analysed_fortran.psyclone_kernels
                                analysed_fortran.psyclone_kernels[kernel_name] = kernel_hash
                    except Exception:
                        pass

            except Exception:
                logger.exception(f'error processing node {obj.item or obj_type} in {fpath}')

        return analysed_fortran

    def _process_use_statement(self, analysed_file, obj):
        use_name = _typed_child(obj, Name, must_exist=True)
        use_name = use_name.string

        if use_name in self.ignore_mod_deps:
            logger.debug(f"ignoring use of {use_name}")
        elif use_name.lower() not in self._intrinsic_modules:
            # found a dependency on fortran
            analysed_file.add_module_dep(use_name)

    def _process_variable_binding(self, analysed_file, obj: Type_Declaration_Stmt):
        # The name keyword on the bind statement is optional.
        # If it doesn't exist, the Fortran variable name is used

        # todo: write and test named variable binding.
        # specs = _typed_child(obj, Attr_Spec_List)
        # bind = _typed_child(specs, Language_Binding_Spec)
        # name = _typed_child(bind, Char_Literal_Constant)
        # if not name:
        #     name = _typed_child(obj, Name)
        #     logger.debug(f"unnamed variable binding, using fortran name '{name}' in {fpath}")
        # else:
        #     logger.debug(f"variable binding called '{name}' in {fpath}")

        entities = _typed_child(obj, Entity_Decl_List)
        for entity in entities.items:
            name = _typed_child(entity, Name)
            analysed_file.add_symbol_def(name.string)

    def _process_comment(self, analysed_file, obj):
        # Handle dependencies from Met Office "DEPENDS ON:" code comments which refer to a c file.
        # Be sure to alert the user that this practice is deprecated.
        # TODO: error handling in case we catch a genuine comment
        # TODO: separate this project-specific code from the generic f analyser?
        depends_str = "DEPENDS ON:"
        if depends_str in obj.items[0]:
            self.depends_on_comment_found = True
            dep = obj.items[0].split(depends_str)[-1].strip()
            # with .o means a c file
            if dep.endswith(".o"):
                analysed_file.mo_commented_file_deps.add(dep.replace(".o", ".c"))
            # without .o means a fortran symbol
            else:
                analysed_file.add_symbol_dep(dep)

    def _process_subroutine_or_function(self, analysed_file, fpath, obj):
        # binding?
        bind = _typed_child(obj, Language_Binding_Spec)
        if bind:
            name = _typed_child(bind, Char_Literal_Constant)
            if not name:
                name = _typed_child(obj, Name)
                logger.debug(f"unnamed binding, using fortran name '{name}' in {fpath}")
            bind_name = name.string.replace('"', '')

            # importing a c function into fortran, i.e binding within an interface block
            if _has_ancestor_type(obj, Interface_Block):
                # found a dependency on C
                logger.debug(f"found function binding import '{bind_name}'")
                analysed_file.add_symbol_dep(bind_name)

            # exporting from fortran to c, i.e binding without an interface block
            else:
                analysed_file.add_symbol_def(bind_name)

        # not bound, just record the presence of the fortran symbol
        # we don't need to record stuff in modules (we think!)
        elif not _has_ancestor_type(obj, Module) and not _has_ancestor_type(obj, Interface_Block):
            if isinstance(obj, Subroutine_Stmt):
                analysed_file.add_symbol_def(str(obj.get_name()))
            if isinstance(obj, Function_Stmt):
                _, name, _, _ = obj.items
                analysed_file.add_symbol_def(name.string)


class FortranParserWorkaround(object):
    """
    Use this class to create a workaround when the third-party Fortran parser is unable to process a valid source file.

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
        self.fpath = fpath
        self.module_defs: Set[str] = set(module_defs or {})
        self.symbol_defs: Set[str] = set(symbol_defs or {})
        self.module_deps: Set[str] = set(module_deps or {})
        self.symbol_deps: Set[str] = set(symbol_deps or {})
        self.mo_commented_file_deps: Set[str] = set(mo_commented_file_deps or [])

    def as_analysed_fortran(self):

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
