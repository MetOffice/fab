# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Fortran language handling classes.
"""
import logging
from abc import abstractmethod, ABC
from pathlib import Path
from typing import Union

from fab import FabException
from fparser.common.readfortran import FortranFileReader  # type: ignore
from fparser.two.Fortran2003 import (  # type: ignore
    Use_Stmt, Module_Stmt, Program_Stmt, Subroutine_Stmt, Function_Stmt, Language_Binding_Spec,
    Char_Literal_Constant, Interface_Block, Name, Comment, Module, Call_Stmt, Only_List, Actual_Arg_Spec_List, Part_Ref)

# todo: what else should we be importing from 2008 instead of 2003? This seems fragile.
from fparser.two.Fortran2008 import (  # type: ignore
    Type_Declaration_Stmt, Attr_Spec_List, Entity_Decl_List)

from fparser.two.parser import ParserFactory  # type: ignore
from fparser.two.utils import FortranSyntaxError  # type: ignore

from fab.parse import ParseException, EmptySourceFile, AnalysedFileBase, AnalysedFortran, AnalysedX90
from fab.util import log_or_dot, file_checksum, by_type

logger = logging.getLogger(__name__)


# todo: a nicer recursion pattern?
def iter_content(obj):
    """
    Return a generator which yields every node in the tree.
    """
    yield obj
    if hasattr(obj, "content"):
        for child in _iter_content(obj.content):
            yield child


def _iter_content(content):
    for obj in content:
        yield obj
        if hasattr(obj, "content"):
            for child in _iter_content(obj.content):
                yield child


def _has_ancestor_type(obj, obj_type):
    # Recursively check if an object has an ancestor of the given type.
    if not obj.parent:
        return False

    if type(obj.parent) == obj_type:
        return True

    return _has_ancestor_type(obj.parent, obj_type)


def _typed_child(parent, child_type, must_exist=False):
    # Look for a child of a certain type.
    # Returns the child or None.
    # Raises ValueError if more than one child of the given type is found.

    children = list(filter(lambda child: type(child) == child_type, parent.children))
    if len(children) > 1:
        raise ValueError(f"too many children found of type {child_type}")

    if children:
        return children[0]

    if must_exist:
        raise FabException(f'Could not find child of type {child_type} in {parent}')
    return None


class FortranAnalyserBase(ABC):
    """
    Base class for Fortran parse-tree analysers.

    """
    _intrinsic_modules = ['iso_fortran_env', 'iso_c_binding']
    RESULT_CLASS = None

    def __init__(self, std="f2008"):
        """
        :param result_class:
            The type (class) of the analysis result. Defined by the subclass.
        :param std:
            The Fortran standard.

        """
        self.f2008_parser = ParserFactory().create(std=std)

        # runtime
        self._prebuild_folder = None

    def run(self, fpath: Path) -> Union[AnalysedFileBase, Exception]:
        """
        Parse the source file and record what we're interested in (subclass specific).

        Reloads previous analysis results if available.

        """
        log_or_dot(logger, f"analysing {fpath}")

        # do we already have analysis results for this file?
        file_hash = file_checksum(fpath).file_hash
        analysis_fpath = self._get_analysis_fpath(fpath, file_hash)
        if analysis_fpath.exists():
            # Load the result file into whatever result class we use.
            loaded_result = self.result_class.load(analysis_fpath)
            if loaded_result:
                # This result might have been created by another user; their prebuild folder copied to ours.
                # If so, the fpath in the result will *not* point to the file we eventually want to compile,
                # it will point to the user's original file, somewhere else. So replace it with our own path.
                loaded_result.fpath = fpath
                return loaded_result

        # parse the file, get a node tree
        node_tree = self._parse_file(fpath=fpath)
        if isinstance(node_tree, Exception):
            return Exception(f"error parsing file '{fpath}': {node_tree}")
        if node_tree.content[0] is None:
            logger.debug(f"  empty tree found when parsing {fpath}")
            # todo: If we don't save the empty result we'll keep analysing it every time!
            return EmptySourceFile(fpath)

        # find things in the node tree
        result = self.walk_nodes(fpath=fpath, file_hash=file_hash, node_tree=node_tree)
        return result

    def _get_analysis_fpath(self, fpath, file_hash) -> Path:
        return Path(self._prebuild_folder / f'{fpath.stem}.{file_hash}.an')

    def _parse_file(self, fpath):
        """Get a node tree from a fortran file."""
        reader = FortranFileReader(str(fpath), ignore_comments=False)
        reader.exit_on_error = False  # don't call sys.exit, it messes up the multi-processing
        try:
            tree = self.f2008_parser(reader)
            return tree
        except FortranSyntaxError as err:
            # we can't return the FortranSyntaxError, it breaks multiprocessing!
            logger.error(f"\nsyntax error in {fpath}\n{err}")
            return Exception(f"syntax error in {fpath}\n{err}")
        except Exception as err:
            logger.error(f"\nunhandled error '{type(err)}' in {fpath}\n{err}")
            return Exception(f"unhandled error '{type(err)}' in {fpath}\n{err}")

    @abstractmethod
    def walk_nodes(self, fpath, file_hash, node_tree) -> AnalysedFileBase:
        """
        Examine the nodes in the parse tree, recording things we're interested in.

        Return type depends on our subclass, and will be a subclass of AnalysedFileBase.

        """
        raise NotImplementedError


class FortranAnalyser(FortranAnalyserBase):
    """
    A build step which analyses a fortran file using fparser2, creating an :class:`~fab.dep_tree.AnalysedFile`.

    """
    def __init__(self, std="f2008", ignore_mod_deps=None):
        super().__init__(std=std)
        self.ignore_mod_deps = ignore_mod_deps or []
        self.depends_on_comment_found = False
        self.result_class = AnalysedFortran

    def walk_nodes(self, fpath, file_hash, node_tree) -> AnalysedFortran:

        # see what's in the tree
        analysed_file = AnalysedFortran(fpath=fpath, file_hash=file_hash)
        for obj in iter_content(node_tree):
            obj_type = type(obj)
            try:

                # todo: ?replace these with function lookup dict[type, func]? - Or the new match statement, Python 3.10
                if obj_type == Use_Stmt:
                    self._process_use_statement(analysed_file, obj)  # raises

                elif obj_type == Call_Stmt:
                    called_name = _typed_child(obj, Name)
                    # called_name will be None for calls like thing%method(),
                    # which is fine as it doesn't reveal a dependency on an external function.
                    if called_name:
                        analysed_file.add_symbol_dep(called_name.string)

                elif obj_type == Program_Stmt:
                    analysed_file.add_symbol_def(str(obj.get_name()))

                elif obj_type == Module_Stmt:
                    analysed_file.add_module_def(str(obj.get_name()))

                elif obj_type in (Subroutine_Stmt, Function_Stmt):
                    self._process_subroutine_or_function(analysed_file, fpath, obj)

                # variables with c binding are found inside a Type_Declaration_Stmt.
                # todo: This was used for exporting a Fortran variable for use in C.
                #       Variable bindings are bidirectional - does this work the other way round, too?
                #       Make sure we have a test for it.
                elif obj_type == Type_Declaration_Stmt:
                    # bound?
                    specs = _typed_child(obj, Attr_Spec_List)
                    if specs and _typed_child(specs, Language_Binding_Spec):
                        self._process_variable_binding(analysed_file, obj)

                elif obj_type == Comment:
                    self._process_comment(analysed_file, obj)

            except Exception:
                logger.exception(f'error processing node {obj.item or obj_type} in {fpath}')

        analysis_fpath = self._get_analysis_fpath(fpath, file_hash)
        analysed_file.save(analysis_fpath)
        return analysed_file

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
            if type(obj) == Subroutine_Stmt:
                analysed_file.add_symbol_def(str(obj.get_name()))
            if type(obj) == Function_Stmt:
                _, name, _, _ = obj.items
                analysed_file.add_symbol_def(name.string)


class X90Analyser(FortranAnalyserBase):

    # Make a fortran compliant version so we can use fortran parsers on it.
    # Use hashing to reuse previous analysis results.

    def __init__(self):
        super().__init__()
        self.result_class = AnalysedX90

        # runtime

        # Maps "only" symbols to the modules they're in.
        self._symbol_deps = {}

    def walk_nodes(self, fpath, file_hash, node_tree) -> AnalysedX90:
        analysed_file = AnalysedX90(fpath=fpath, file_hash=file_hash)

        for obj in iter_content(node_tree):
            obj_type = type(obj)
            try:
                if obj_type == Use_Stmt:
                    self._process_use_statement(analysed_file, obj)  # raises

                elif obj_type == Call_Stmt:
                    self._process_call_statement(analysed_file, obj)

            except Exception:
                logger.exception(f'error processing node {obj.item or obj_type} in {fpath}')

        # analysis_fpath = self._get_analysis_fpath(fpath, file_hash)
        # analysed_file.save(analysis_fpath)

        return analysed_file

    def _process_use_statement(self, analysed_file, obj):
        # Record the modules in which potential kernels live.
        # We'll find out if they're kernels later.
        module_dep = _typed_child(obj, Name, must_exist=True)
        only_list = _typed_child(obj, Only_List)
        if not only_list:
            return

        name_nodes = by_type(only_list.children, Name)
        for name in name_nodes:
            self._symbol_deps[name.string] = module_dep.string

    def _process_call_statement(self, analysed_file, obj):
        # if we're calling invoke, record the names of the args.
        # sanity check they end with "_type".
        called_name = _typed_child(obj, Name)
        if called_name.string == "invoke":
            arg_list = _typed_child(obj, Actual_Arg_Spec_List)
            if not arg_list:
                logger.info(f'No arg list passed to invoke: {obj.string}')
                return
            args = by_type(arg_list.children, Part_Ref)
            for arg in args:
                arg_name = _typed_child(arg, Name)
                arg_name = arg_name.string
                if arg_name in self._symbol_deps:
                    in_mod = self._symbol_deps[arg_name]
                    print(f'found kernel dependency {arg_name} in module {in_mod}')
                    # analysed_file.add_kernel_dep(arg)
                else:
                    print(f"arg '{arg_name}' to invoke() was not used, presumed built-in kernel")
