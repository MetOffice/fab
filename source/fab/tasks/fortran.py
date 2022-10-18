# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
"""
Fortran language handling classes.
"""
import logging
from pathlib import Path

from fparser.common.readfortran import FortranFileReader  # type: ignore
from fparser.two.Fortran2003 import (  # type: ignore
    Use_Stmt, Module_Stmt, Program_Stmt, Subroutine_Stmt, Function_Stmt, Language_Binding_Spec,
    Char_Literal_Constant, Interface_Block, Name, Comment, Module, Call_Stmt)

# todo: what else should we be importing from 2008 instead of 2003? This seems fragile.
from fparser.two.Fortran2008 import (  # type: ignore
    Type_Declaration_Stmt, Attr_Spec_List, Entity_Decl_List)

from fparser.two.parser import ParserFactory  # type: ignore
from fparser.two.utils import FortranSyntaxError  # type: ignore

from fab.dep_tree import AnalysedFile, EmptySourceFile
from fab.tasks import TaskException
from fab.util import log_or_dot, file_checksum

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


def _typed_child(parent, child_type):
    # Look for a child of a certain type.
    # Returns the child or None.
    # Raises ValueError if more than one child of the given type is found.

    children = list(filter(lambda child: type(child) == child_type, parent.children))
    if len(children) > 1:
        raise ValueError(f"too many children found of type {child_type}")

    if children:
        return children[0]
    return None


class FortranAnalyser(object):
    """
    A build step which analyses a fortran file using fparser2, creating an :class:`~fab.dep_tree.AnalysedFile`.

    """
    _intrinsic_modules = ['iso_fortran_env', 'iso_c_binding']

    def __init__(self, std="f2008", ignore_mod_deps=None):
        self.f2008_parser = ParserFactory().create(std=std)
        self.ignore_mod_deps = ignore_mod_deps or []

        # Warn the user if the code still includes this deprecated dependency mechanism
        self.depends_on_comment_found = False

        # runtime
        self._prebuild_folder = None

    def run(self, fpath: Path):
        log_or_dot(logger, f"analysing {fpath}")

        # do we already have analysis results for this file?
        # todo: dupe - probably best in a parser base class
        file_hash = file_checksum(fpath).file_hash
        analysis_fpath = Path(self._prebuild_folder / f'{fpath.stem}.{file_hash}.an')
        if analysis_fpath.exists():
            loaded_result = AnalysedFile.load(analysis_fpath)
            # Note: This result might have been created by another user, and the prebuild copied here.
            # If so, the fpath in the result will *not* point to the file we eventually want to compile,
            # it will point to the user's original file, somewhere else. So, replace it with our own path.
            loaded_result.fpath = fpath
            return loaded_result

        analysed_file = AnalysedFile(fpath=fpath, file_hash=file_hash)

        # parse the file
        parse_result = self._parse_file(fpath=fpath)
        if isinstance(parse_result, Exception):
            return parse_result

        if parse_result.content[0] is None:
            logger.debug(f"  empty tree found when parsing {fpath}")
            return EmptySourceFile(fpath)

        # see what's in the tree
        for obj in iter_content(parse_result):
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

        analysed_file.save(analysis_fpath)
        return analysed_file

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

    def _process_use_statement(self, analysed_file, obj):
        use_name = _typed_child(obj, Name)
        if not use_name:
            raise TaskException("ERROR finding name in use statement:", obj.string)

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
