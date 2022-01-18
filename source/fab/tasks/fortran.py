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
from fab.util import log_or_dot, HashedFile, CompiledFile


def iter_content(obj):
    """
    Recursively iterate through everything in an fparser object's content heirarchy.   
    """
    if not hasattr(obj, "content"):
        return
    for child in obj.content:
        yield child
        for grand_child in iter_content(child):
            yield grand_child


def has_ancestor_type(obj, obj_type):
    """Recursively check if an object has an ancestor of the given type."""
    if not obj.parent:
        return False

    if type(obj.parent) == obj_type:
        return True

    return has_ancestor_type(obj.parent, obj_type)


def typed_child(parent, child_type):
    """
    Look for a child of a certain type.

    Returns the child or None.
    Raises ValueError if more than one child of the given type is found.
    """
    children = list(filter(lambda child: type(child) == child_type, parent.children))
    if len(children) > 1:
        raise ValueError(f"too many children found of type {child_type}")
    return (children or [None])[0]


class FortranAnalyser(object):

    _intrinsic_modules = ['iso_fortran_env']

    def __init__(self):
        # todo: fortran version in config?
        self.f2008_parser = ParserFactory().create(std="f2008")

        # Warn the user if the code still includes this deprecated dependency mechanism
        self.depends_on_comment_found = False

    def run(self, hashed_file: HashedFile):

        fpath, file_hash = hashed_file
        logger = logging.getLogger(__name__)
        log_or_dot(logger, f"analysing {fpath}")

        # parse the fortran into a tree
        # todo: Matthew said there's a lightweight read mode coming?
        reader = FortranFileReader(str(fpath), ignore_comments=False)
        reader.exit_on_error = False  # don't call sys.exit, it messes up the multi-processing
        try:
            tree = self.f2008_parser(reader)
        except FortranSyntaxError as err:
            # we can't return the FortranSyntaxError, it breaks multiprocessing!
            logger.error(f"\nsyntax error in {fpath}\n{err}")
            return Exception(f"syntax error in {fpath}\n{err}")
        except Exception as err:
            logger.error(f"\nunhandled error '{type(err)}' in {fpath}\n{err}")
            return Exception(f"unhandled error '{type(err)}' in {fpath}\n{err}")

        # did it find anything?
        if tree.content[0] == None:
            logger.debug(f"  empty tree found when parsing {fpath}")
            return EmptySourceFile(fpath)

        analysed_file = AnalysedFile(fpath=fpath, file_hash=file_hash)



        # TODO:
        # - parse external symbol defs -> add symbol dep
        # - ? record ALL top level things, including functions, which externs can then refer to ?
        #   - ? or just force non module stuff to use the undeclared deps list ?


        # see what else is in the tree
        for obj in iter_content(tree):
            obj_type = type(obj)
            
            # including a module
            if obj_type == Use_Stmt:
                use_name = typed_child(obj, Name)
                if not use_name:
                    return TaskException("ERROR finding name in use statement:", obj.string)
                use_name = use_name.string

                if use_name not in self._intrinsic_modules:
                    # found a dependency on fortran
                    analysed_file.add_symbol_dep(use_name)

            # defining a module or program
            elif obj_type in (Module_Stmt, Program_Stmt):
                analysed_file.add_symbol_def(str(obj.get_name()))

            # function
            elif obj_type in (Subroutine_Stmt, Function_Stmt):
                # binding?
                bind = typed_child(obj, Language_Binding_Spec)
                if bind:
                    name = typed_child(bind, Char_Literal_Constant)
                    if not name:
                        name = typed_child(obj, Name)
                        logger.info(f"Warning: unnamed binding, using fortran name '{name}' in {fpath}")
                        # # TODO: use the fortran name, lower case
                        # return TaskException(f"Error getting name of function binding: {obj.string} in {fpath}")
                    bind_name = name.string.replace('"', '')

                    # importing a c function into fortran, i.e binding within an interface block
                    if has_ancestor_type(obj, Interface_Block):
                        # found a dependency on C
                        logger.debug(f"found function binding import '{bind_name}'")
                        analysed_file.add_symbol_dep(bind_name)

                    # exporting from fortran to c, i.e binding without an interface block
                    else:
                        analysed_file.add_symbol_def(bind_name)

                # not bound, just record the presence of the fortran symbol
                # we don't need to record stuff in modules (we think!)
                elif not has_ancestor_type(obj, Module) and not has_ancestor_type(obj, Interface_Block):
                    if obj_type == Subroutine_Stmt:
                        analysed_file.add_symbol_def(str(obj.get_name()))
                    if obj_type == Function_Stmt:
                        _, name, _, _ = obj.items
                        analysed_file.add_symbol_def(name.string)

            elif obj_type == "foo":
                return NotImplementedError(f"variable bindings not yet implemented {fpath}")

                # This should be a line binding from C to a variable definition
                # (procedure binds are dealt with above)
                # The name keyword on the bind statement is optional.
                # If it doesn't exist, the Fortran variable name is used

                # logger.debug('Found C bound variable called "%s"', bind_name)

                # Add to the C database
                # symbol_id = CSymbolID(cbind_name, reader.filename)
                # cstate.add_c_symbol(symbol_id)
                # new_artifact.add_definition(cbind_name)

            # Handle dependencies from Met Office "DEPENDS ON:" code comments which refer to a c file.
            # Be sure to alert the user that this practice is deprecated.
            # TODO: error handling in case we catch a genuine comment
            # TODO: separate this project-specific code from the generic f analyser?
            elif obj_type == Comment:
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

        logger.debug(f"    analysed {analysed_file.fpath}")
        return analysed_file


class FortranCompiler(object):

    def __init__(self, compiler: List[str], flags: FlagsConfig, workspace: Path, debug_skip: bool):
        self._compiler = compiler
        self._flags = flags
        self._workspace = workspace
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
            res = subprocess.run(command, capture_output=True)
            if res.returncode != 0:
                # todo: specific exception
                return Exception(f"The compiler exited with non zero: {res.stderr.decode()}")
        # todo: not idiomatic
        except Exception as err:
            # todo: specific exception
            return Exception("Error calling compiler:", err)

        return CompiledFile(analysed_file, output_fpath)
