# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
"""
Fortran language handling classes.
"""
import logging
from pathlib import Path
import subprocess
from time import perf_counter
from typing import (Generator,
                    Iterator,
                    List,
                    Match,
                    Optional,
                    Pattern,
                    Sequence,
                    Tuple,
                    Union, Dict, Set)
from fparser.two.Fortran2003 import Char_Literal_Constant, Function_Stmt, Interface_Block, Language_Binding_Spec, Module_Stmt, Name, Program_Stmt, Subroutine_Stmt, Use_Stmt

from fparser.two.parser import ParserFactory
from fparser.common.readfortran import FortranFileReader

from fab.database import (DatabaseDecorator,
                          FileInfoDatabase,
                          StateDatabase,
                          SqliteStateDatabase,
                          WorkingStateException)
from fab.tasks import \
    Task, \
    TaskException, timed_method
from fab.tasks.c import CWorkingState, CSymbolID
from fab.reader import TextReader, TextReaderDecorator, FileTextReader
from fab.artifact import \
    Artifact, \
    Analysed, \
    Raw, \
    Compiled, \
    BinaryObject
from fab.tree import ProgramUnit, EmptyProgramUnit
from fab.util import log_or_dot


class FortranUnitUnresolvedID(object):
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other):
        if not isinstance(other, FortranUnitUnresolvedID):
            message = "Cannot compare FortranUnitUnresolvedID with " \
                + other.__class__.__name__
            raise TypeError(message)
        return other.name == self.name


class FortranUnitID(FortranUnitUnresolvedID):
    def __init__(self, name: str, found_in: Path):
        super().__init__(name)
        self.found_in = found_in

    def __hash__(self):
        return hash(self.name) + hash(self.found_in)

    def __eq__(self, other):
        if not isinstance(other, FortranUnitID):
            message = "Cannot compare FortranUnitID with " \
                + other.__class__.__name__
            raise TypeError(message)
        return super().__eq__(other) and other.found_in == self.found_in


class FortranInfo(object):
    def __init__(self,
                 unit: FortranUnitID,
                 depends_on: Sequence[str] = ()):
        self.unit = unit
        self.depends_on = list(depends_on)

    def __str__(self):
        return f"Fortran program unit '{self.unit.name}' " \
            f"from '{self.unit.found_in}' depending on: " \
            f"{', '.join(self.depends_on)}"

    def __eq__(self, other):
        if not isinstance(other, FortranInfo):
            message = "Cannot compare Fortran Info with " \
                + other.__class__.__name__
            raise TypeError(message)
        return other.unit == self.unit and other.depends_on == self.depends_on

    def add_prerequisite(self, prereq: str):
        self.depends_on.append(prereq)


class FortranWorkingState(DatabaseDecorator):
    """
    Maintains a database of information relating to Fortran program units.
    """
    # According to the Fortran spec, section 3.2.2 in
    # BS ISO/IEC 1539-1:2010, the maximum size of a name is 63 characters.
    #
    # If you find source containing labels longer than this then that source
    # is non-conformant.
    #
    _FORTRAN_LABEL_LENGTH: int = 63

    def __init__(self, database: StateDatabase):
        super().__init__(database)
        create_unit_table = [
            f'''create table if not exists fortran_unit (
                   id integer primary key,
                   unit character({self._FORTRAN_LABEL_LENGTH}) not null,
                   found_in character({FileInfoDatabase.PATH_LENGTH})
                       references file_info (filename)
                   )''',
            '''create index if not exists idx_fortran_program_unit
                   on fortran_unit (unit, found_in)'''
        ]
        self.execute(create_unit_table, {})

        # Although the current unit will already have been entered into the
        # database it is not necessarily unique. We may have multiple source
        # files which define identically named units. Thus it can not be used
        # as a foreign key alone.
        #
        # Meanwhile the dependency unit may not have been encountered yet so
        # we can't expect it to be in the database. Thus it too may not be
        # used as a foreign key.
        #
        create_prerequisite_table = [
            f'''create table if not exists fortran_prerequisite (
                id integer primary key,
                unit character({self._FORTRAN_LABEL_LENGTH}) not null,
                found_in character({FileInfoDatabase.PATH_LENGTH}) not null,
                prerequisite character({self._FORTRAN_LABEL_LENGTH}) not null,
                foreign key (unit, found_in)
                references fortran_unit (unit, found_in)
                )'''
        ]
        self.execute(create_prerequisite_table, {})

    def __iter__(self) -> Generator[FortranInfo, None, None]:
        """
        Yields all units and their containing file names.

        :return: Object per unit.
        """
        query = '''select u.unit as name, u.found_in, p.prerequisite as prereq
                   from fortran_unit as u
                   left join fortran_prerequisite as p
                   on p.unit = u.unit and p.found_in = u.found_in
                   order by u.unit, u.found_in, p.prerequisite'''
        rows = self.execute([query], {})
        info: Optional[FortranInfo] = None
        key: FortranUnitID = FortranUnitID('', Path())
        for row in rows:
            if FortranUnitID(row['name'], Path(row['found_in'])) == key:
                if info is not None:
                    info.add_prerequisite(row['prereq'])
            else:  # (row['name'], row['found_in']) != key
                if info is not None:
                    yield info
                key = FortranUnitID(row['name'], Path(row['found_in']))
                info = FortranInfo(key)
                if row['prereq']:
                    info.add_prerequisite(row['prereq'])
        if info is not None:  # We have left-overs
            yield info

    def add_fortran_program_unit(self, unit: FortranUnitID) -> None:
        """
        Creates a record of a new program unit and the file it is found in.

        Note that the filename is absolute meaning that if you rename or move
        the source directory nothing will match up.

        :param unit: Program unit identifier.
        """
        add_unit = [
            '''insert into fortran_unit (unit, found_in)
                   values (:unit, :filename)'''
        ]
        self.execute(add_unit,
                     {'unit': unit.name, 'filename': str(unit.found_in)})

    def add_fortran_dependency(self,
                               unit: FortranUnitID,
                               depends_on: str) -> None:
        """
        Records the dependency of one unit on another.

        :param unit: Program unit identifier.
        :param depends_on: Name of the prerequisite unit.
        """
        add_dependency = [
            '''insert into fortran_prerequisite(unit, found_in, prerequisite)
                   values (:unit, :found_in, :depends_on)'''
        ]
        self.execute(add_dependency, {'unit': unit.name,
                                      'found_in': str(unit.found_in),
                                      'depends_on': depends_on})

    def remove_fortran_file(self, filename: Union[Path, str]) -> None:
        """
        Removes all records relating of a particular source file.

        :param filename: File to be removed.
        """
        remove_file = [
            '''delete from fortran_prerequisite
               where found_in = :filename''',
            '''delete from fortran_unit where found_in=:filename'''
            ]
        self.execute(remove_file, {'filename': str(filename)})

    def get_program_unit(self, name: str) -> List[FortranInfo]:
        """
        Gets the details of program units given their name.

        It is possible that identically named program units appear in multiple
        files, hence why a list is returned. It would be an error to try
        linking these into a single executable but that is not a concern for
        the model of the source tree.

        :param name: Program unit name.
        :return: List of unit information objects.
        """
        query = '''select u.unit, u.found_in, p.prerequisite
                   from fortran_unit as u
                   left join fortran_prerequisite as p
                   on p.unit = u.unit and p.found_in = u.found_in
                   where u.unit=:unit
                   order by u.unit, u.found_in, p.prerequisite'''
        rows = self.execute(query, {'unit': name})
        info_list: List[FortranInfo] = []
        previous_id = None
        info: Optional[FortranInfo] = None
        for row in rows:
            unit_id = FortranUnitID(row['unit'], Path(row['found_in']))
            if previous_id is not None and unit_id == previous_id:
                if info is not None:
                    info.add_prerequisite(row['prerequisite'])
            else:  # unit_id != previous_id
                if info is not None:
                    info_list.append(info)
                info = FortranInfo(unit_id)
                if row['prerequisite'] is not None:
                    info.add_prerequisite((row['prerequisite']))
                previous_id = unit_id
        if info is not None:  # We have left overs
            info_list.append(info)
        if len(info_list) == 0:
            message = 'Program unit "{unit}" not found in database.'
            raise WorkingStateException(message.format(unit=name))
        return info_list

    def depends_on(self, unit: FortranUnitID)\
            -> Generator[FortranUnitID, None, None]:
        """
        Gets the prerequisite program units of a program unit.

        :param unit: Program unit identifier.
        :return: Prerequisite unit names. May be an empty list.
        """
        query = '''select p.prerequisite, u.found_in
                   from fortran_prerequisite as p
                   left join fortran_unit as u on u.unit = p.prerequisite
                   where p.unit=:unit and p.found_in=:filename
                   order by p.unit, u.found_in'''
        rows = self.execute(query, {'unit': unit.name,
                                    'filename': str(unit.found_in)})
        for row in rows:
            if row['found_in'] is None:
                yield FortranUnitUnresolvedID(row['prerequisite'])
            else:  # row['found_in'] is not None
                yield FortranUnitID(row['prerequisite'], Path(row['found_in']))


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

    def __init__(self, workspace: Path):
        self.database = SqliteStateDatabase(workspace)
        self.f2008_parser = ParserFactory().create(std="f2008")

    # @timed_method
    def run(self, fpath: Path):
        logger = logging.getLogger(__name__)

        state = FortranWorkingState(self.database)
        state.remove_fortran_file(fpath)
        # If this file defines any C symbol bindings it may also
        # end up with an entry in the C part of the database
        cstate = CWorkingState(self.database)
        cstate.remove_c_file(fpath)

        # new_artifact = Artifact(fpath, artifact.filetype, Analysed)
        program_unit = None
        # logger.debug(f"analysing {fpath}")
        log_or_dot(logger, f"analysing {fpath}")

        # parse the fortran into a tree
        reader = FortranFileReader(str(fpath))  # ignore_comments=False
        tree = self.f2008_parser(reader)
        if tree.content[0] == None:
            logger.debug(f"Empty tree found when parsing {fpath}")
            return EmptyProgramUnit(fpath)

        module_name = None
        deps = set()

        # find the top level program unit first
        for obj in iter_content(tree):
            if type(obj) in [Module_Stmt, Program_Stmt, Function_Stmt, Subroutine_Stmt]:
                module_name = str(obj.get_name())

                unit_id = FortranUnitID(module_name, fpath)
                state.add_fortran_program_unit(unit_id)
                program_unit = ProgramUnit(module_name, fpath)
                break
        if not module_name:
            return RuntimeError("Error finding top level program unit")
            # raise RuntimeError("Error finding top level program unit")


        # see what else is in the tree
        for obj in iter_content(tree):
            obj_type = type(obj)
            
            if obj_type == Use_Stmt:
                use_name = typed_child(obj, Name)
                if not use_name:
                    raise TaskException("ERROR finding name in use statement:", obj.string)
                use_name = use_name.string

                if use_name not in self._intrinsic_modules and use_name not in deps:
                    # found a new dependency
                    unit_id = FortranUnitID(module_name, fpath)
                    state.add_fortran_dependency(unit_id, use_name)
                    program_unit.add_dep(use_name)
                    deps.add(use_name)

            elif obj_type == Function_Stmt:
                bind = typed_child(obj, Language_Binding_Spec)
                if bind:
                    name = typed_child(bind, Char_Literal_Constant)
                    if not name:
                        raise TaskException(f"Could not get name of function binding: {obj.string}")
                    bind_name = name.string

                    # importing a c function into fortran, i.e binding within an interface block
                    if has_ancestor_type(obj, Interface_Block):
                        logger.debug(f"function binding import {bind_name}")

                        # TODO: This is sort of hijacking the mechanism used
                        # for Fortran module dependencies, only using the
                        # symbol name. Longer term we probably need a more
                        # elegant solution
                        # TODO: what if this is also the program unit? Check if that's possible /ok.
                        unit_id = FortranUnitID(module_name, fpath)
                        state.add_fortran_dependency(unit_id, bind_name)
                        program_unit.add_dep(bind_name)

                    # exporting from fortran to c, i.e binding without an interface block
                    else:
                        logger.debug(f"function binding export {bind_name}")
                        # TODO: this does not occur in jules, so is not yet tested on a real repo
                        # Add to the C database
                        symbol_id = CSymbolID(bind_name, fpath)
                        cstate.add_c_symbol(symbol_id)
                        program_unit.add_dep(bind_name)

            # TODO: (NOT PRESENT IN JULES) variable binding
            elif obj_type == "foo":
                raise NotImplementedError

                # This should be a line binding from C to a variable definition
                # (procedure binds are dealt with above)
                # The name keyword on the bind statement is optional.
                # If it doesn't exist, the Fortran variable name is used

                # logger.debug('Found C bound variable called "%s"', bind_name)

                # Add to the C database
                # symbol_id = CSymbolID(cbind_name, reader.filename)
                # cstate.add_c_symbol(symbol_id)
                # new_artifact.add_definition(cbind_name)

        logger.debug(f"    analysed {program_unit.name}")
        return program_unit


class FortranPreProcessor(object):
    def __init__(self,
                 preprocessor: str,
                 flags: List[str],
                 workspace: Path,
                 skip_if_exists: bool = False):
        self._preprocessor = preprocessor
        self._flags = flags
        self._workspace = workspace
        self._skip_if_exists = skip_if_exists

    # @timed_method
    def run(self, fpath: Path, source_root: Path):
        logger = logging.getLogger(__name__)

        # if len(artifacts) == 1:
        #     artifact = artifacts[0]
        # else:
        #     msg = ('Fortran Preprocessor expects only one Artifact, '
        #            f'but was given {len(artifacts)}')
        #     raise TaskException(msg)

        command = [self._preprocessor]
        command.extend(self._flags)

        # find ancillary inc files already copied across
        command.extend(["-I", str(self._workspace)])  # todo: revisit this

        command.append(str(fpath))

        # todo: add utils & src!!
        # output_fpath = (self._workspace / fpath.with_suffix('.f90').name)
        rel_fpath = fpath.relative_to(source_root)
        output_fpath = (self._workspace / rel_fpath.with_suffix('.f90'))
        command.append(str(output_fpath))

        if self._skip_if_exists and output_fpath.exists():
            log_or_dot(logger, f'Preprocessor skipping {output_fpath}')
        else:
            log_or_dot(logger, 'Preprocessor running command: ' + ' '.join(command))
            try:
                subprocess.run(command, check=True, capture_output=True)
            except subprocess.CalledProcessError as err:
                return Exception(f"Error running preprocessor command: {command}\n{err.stderr}")

        return output_fpath


# todo: better as a named tuple?
class CompiledProgramUnit(object):
    def __init__(self, program_unit, output_fpath):
        self.program_unit = program_unit
        self.output_fpath = output_fpath


class FortranCompiler(object):

    def __init__(self,
                 compiler: str,
                 flags: List[str],
                 workspace: Path,
                 skip_if_exists: bool = False):
        self._compiler = compiler
        self._flags = flags
        self._workspace = workspace
        self._skip_if_exists = skip_if_exists

    # @timed_method
    def run(self, program_unit: ProgramUnit):
        logger = logging.getLogger(__name__)

        command = [self._compiler]
        command.extend(self._flags)
        command.append(str(program_unit.fpath))

        output_fpath = (self._workspace / program_unit.fpath.with_suffix('.o').name)
        command.extend(['-o', str(output_fpath)])

        if self._skip_if_exists and output_fpath.exists():
            log_or_dot(logger, f'Compiler skipping {output_fpath}')
        else:
            log_or_dot(logger, 'Compiler running command: ' + ' '.join(command))
            try:
                res = subprocess.run(command, check=True)
                if res.returncode != 0:
                    # todo: specific exception
                    return Exception("The compiler exited with non zero")
            # todo: not idiomatic
            except Exception as err:
                # todo: specific exception
                return Exception("Error calling compiler:", err)

        return CompiledProgramUnit(program_unit, output_fpath)
