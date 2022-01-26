# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
"""
Fortran language handling classes.
"""
import logging
from pathlib import Path
import subprocess
from typing import Generator, List, Optional, Sequence, Union

from fparser.two.Fortran2003 import Use_Stmt, Module_Stmt, Program_Stmt, Subroutine_Stmt, Function_Stmt, \
    Language_Binding_Spec, Char_Literal_Constant, Interface_Block, Name, Comment, Module
from fparser.two.parser import ParserFactory
from fparser.common.readfortran import FortranFileReader
from fparser.two.utils import FortranSyntaxError

from fab.config_sketch import FlagsConfig
from fab.tasks import  TaskException

from fab.dep_tree import AnalysedFile, EmptySourceFile
from fab.util import log_or_dot, HashedFile, CompiledFile, run_command

logger = logging.getLogger(__name__)


# todo: a nicer way?
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
    _intrinsic_modules = ['iso_fortran_env']

    def __init__(self):
        # todo: fortran version in config?
        self.f2008_parser = ParserFactory().create(std="f2008")

        # Warn the user if the code still includes this deprecated dependency mechanism
        self.depends_on_comment_found = False

    def run(self, hashed_file: HashedFile):
        fpath, file_hash = hashed_file
        log_or_dot(logger, f"analysing {fpath}")

        # parse the file
        try:
            tree = self._parse_file(fpath=fpath)
        except Exception as err:
            return err
        if tree.content[0] is None:
            logger.debug(f"  empty tree found when parsing {fpath}")
            return EmptySourceFile(fpath)

        analysed_file = AnalysedFile(fpath=fpath, file_hash=file_hash)

        # see what's in the tree
        try:
            for obj in iter_content(tree):
                obj_type = type(obj)

                # todo: ?replace these with function lookup dict[type, func]?
                if obj_type == Use_Stmt:
                    self._process_use_statement(analysed_file, obj)  ## raises

                elif obj_type in (Module_Stmt, Program_Stmt):
                    analysed_file.add_symbol_def(str(obj.get_name()))

                elif obj_type in (Subroutine_Stmt, Function_Stmt):
                    self._process_subroutine_or_function(analysed_file, fpath, obj)

                # todo: we've not needed this so far, for jules or um...
                elif obj_type == "variable binding not yet supported":
                    return self._process_variable_binding(fpath)

                elif obj_type == Comment:
                    self._process_comment(analysed_file, obj)

        except Exception as err:
            return err

        logger.debug(f"    analysed {analysed_file.fpath}")
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
            raise Exception(f"syntax error in {fpath}\n{err}")
        except Exception as err:
            logger.error(f"\nunhandled error '{type(err)}' in {fpath}\n{err}")
            raise Exception(f"unhandled error '{type(err)}' in {fpath}\n{err}")

    def _process_use_statement(self, analysed_file, obj):
        use_name = _typed_child(obj, Name)
        if not use_name:
            raise TaskException("ERROR finding name in use statement:", obj.string)
        use_name = use_name.string

        if use_name not in self._intrinsic_modules:
            # found a dependency on fortran
            analysed_file.add_symbol_dep(use_name)

    def _process_variable_binding(self, fpath):
        # This should be a line binding from C to a variable definition
        # (procedure binds are dealt with above)
        # The name keyword on the bind statement is optional.
        # If it doesn't exist, the Fortran variable name is used
        # logger.debug('Found C bound variable called "%s"', bind_name)
        # Add to the C database
        # symbol_id = CSymbolID(cbind_name, reader.filename)
        # cstate.add_c_symbol(symbol_id)
        # new_artifact.add_definition(cbind_name)
        return NotImplementedError(f"variable bindings not yet implemented {fpath}")

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
                logger.info(f"Warning: unnamed binding, using fortran name '{name}' in {fpath}")
                # # TODO: use the fortran name, lower case
                # return TaskException(f"Error getting name of function binding: {obj.string} in {fpath}")
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


class FortranCompiler(object):
    """
    A build step which calls a fortran compiler.

    """
    def __init__(self, compiler: List[str], flags: FlagsConfig, debug_skip=False):
        """

        Args:
            - compiler: E.g 'gfortran' or 'mpifort'
            - flags: Config object defining common and per-path flags.
            - debug_skip: Ignore this for now!

        """
        self._compiler = compiler
        self._flags = flags
        self.debug_skip = debug_skip

    # @timed_method
    def run(self, analysed_file: AnalysedFile):
        logger = logging.getLogger(__name__)

        command = [*self._compiler]

        command.extend(self._flags.flags_for_path(analysed_file.fpath))

        command.append(str(analysed_file.fpath))

        output_fpath = analysed_file.fpath.with_suffix('.o')
        if self.debug_skip and output_fpath.exists():
            log_or_dot(logger, f'Compiler skipping: {output_fpath}')
            return CompiledFile(analysed_file, output_fpath)

        command.extend(['-o', str(output_fpath)])

        # logger.info(program_unit.name)
        log_or_dot(logger, 'Compiler running command: ' + ' '.join(command))
        try:
            # res = subprocess.run(command, capture_output=True)
            # if res.returncode != 0:
            #     return Exception(f"The compiler exited with non zero: {res.stderr.decode()}")
            run_command(command)
        except Exception as err:
            return Exception("Error calling compiler:", err)

        return CompiledFile(analysed_file, output_fpath)
