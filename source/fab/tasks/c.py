# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
"""
C language handling classes.
"""
import logging
import shutil
import subprocess
import re
import clang.cindex  # type: ignore
from collections import deque
from typing import \
    List, \
    Iterator, \
    Pattern, \
    Optional, \
    Match, \
    Sequence, \
    Generator, \
    Union
from pathlib import Path

from config_sketch import FlagsConfig
from fab.dep_tree import AnalysedFile

from fab.constants import SOURCE_ROOT, BUILD_OUTPUT, BUILD_SOURCE

from fab.database import \
    StateDatabase, \
    DatabaseDecorator, \
    FileInfoDatabase, \
    WorkingStateException
from fab.tasks import Task, TaskException

from fab.reader import \
    TextReader, \
    FileTextReader, \
    TextReaderDecorator
from fab.util import log_or_dot, HashedFile, CompiledFile, fixup_command_includes, input_to_output_fpath


class CSymbolUnresolvedID(object):
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other):
        if not isinstance(other, CSymbolUnresolvedID):
            message = "Cannot compare CSymbolUnresolvedID with " \
                + other.__class__.__name__
            raise TypeError(message)
        return other.name == self.name


class CSymbolID(CSymbolUnresolvedID):
    def __init__(self, name: str, found_in: Path):
        super().__init__(name)
        self.found_in = found_in

    def __hash__(self):
        return hash(self.name) + hash(self.found_in)

    def __eq__(self, other):
        if not isinstance(other, CSymbolID):
            message = "Cannot compare CSymbolID with " \
                + other.__class__.__name__
            raise TypeError(message)
        return super().__eq__(other) and other.found_in == self.found_in


class CInfo(object):
    def __init__(self,
                 symbol: CSymbolID,
                 depends_on: Sequence[str] = ()):
        self.symbol = symbol
        self.depends_on = list(depends_on)

    def __str__(self):
        return f"C symbol '{self.symbol.name}' " \
            f"from '{self.symbol.found_in}' depending on: " \
            f"{', '.join(self.depends_on)}"

    def __eq__(self, other):
        if not isinstance(other, CInfo):
            message = "Cannot compare C Info with " \
                + other.__class__.__name__
            raise TypeError(message)
        return other.symbol == self.symbol \
            and other.depends_on == self.depends_on

    def add_prerequisite(self, prereq: str):
        self.depends_on.append(prereq)


class CWorkingState(DatabaseDecorator):
    """
    Maintains a database of information relating to C symbols.
    """
    # According to the C standard, section 5.2.4.1,
    # (C11) ISO/IEC 9899, the maximum length of an
    # external identifier is 31 characters.
    #
    _C_LABEL_LENGTH: int = 31

    def __init__(self, database: StateDatabase):
        super().__init__(database)
        create_symbol_table = [
            f'''create table if not exists c_symbol (
                   id integer primary key,
                   symbol character({self._C_LABEL_LENGTH}) not null,
                   found_in character({FileInfoDatabase.PATH_LENGTH})
                       references file_info (filename)
                   )''',
            '''create index if not exists idx_c_symbol
                   on c_symbol (symbol, found_in)'''
        ]
        self.execute(create_symbol_table, {})

        # Although the current symbol will already have been entered into the
        # database it is not necessarily unique. We may have multiple source
        # files which define identically named symbols. Thus it can not be used
        # as a foreign key alone.
        #
        # Meanwhile the dependency symbol may not have been encountered yet so
        # we can't expect it to be in the database. Thus it too may not be
        # used as a foreign key.
        #
        create_prerequisite_table = [
            f'''create table if not exists c_prerequisite (
                id integer primary key,
                symbol character({self._C_LABEL_LENGTH}) not null,
                found_in character({FileInfoDatabase.PATH_LENGTH}) not null,
                prerequisite character({self._C_LABEL_LENGTH}) not null,
                foreign key (symbol, found_in)
                references c_symbol (symbol, found_in)
                )'''
        ]
        self.execute(create_prerequisite_table, {})

    def __iter__(self) -> Generator[CInfo, None, None]:
        """
        Yields all symbols and their containing file names.
        :return: Object per symbol.
        """
        query = '''select s.symbol as name, s.found_in, p.prerequisite as prereq
                   from c_symbol as s
                   left join c_prerequisite as p
                   on p.symbol = s.symbol and p.found_in = s.found_in
                   order by s.symbol, s.found_in, p.prerequisite'''
        rows = self.execute([query], {})
        info: Optional[CInfo] = None
        key: CSymbolID = CSymbolID('', Path())
        for row in rows:
            if CSymbolID(row['name'], Path(row['found_in'])) == key:
                if info is not None:
                    info.add_prerequisite(row['prereq'])
            else:  # (row['name'], row['found_in']) != key
                if info is not None:
                    yield info
                key = CSymbolID(row['name'], Path(row['found_in']))
                info = CInfo(key)
                if row['prereq']:
                    info.add_prerequisite(row['prereq'])
        if info is not None:  # We have left-overs
            yield info

    def add_c_symbol(self, symbol: CSymbolID) -> None:
        """
        Creates a record of a new symbol and the file it is found in.
        Note that the filename is absolute meaning that if you rename or move
        the source directory nothing will match up.
        :param symbol: symbol identifier.
        """
        add_symbol = [
            '''insert into c_symbol (symbol, found_in)
                   values (:symbol, :filename)'''
        ]
        self.execute(add_symbol,
                     {'symbol': symbol.name,
                      'filename': str(symbol.found_in)})

    def add_c_dependency(self,
                         symbol: CSymbolID,
                         depends_on: str) -> None:
        """
        Records the dependency of one symbol on another.
        :param symbol: symbol identifier.
        :param depends_on: Name of the prerequisite symbol.
        """
        add_dependency = [
            '''insert into c_prerequisite(symbol, found_in, prerequisite)
                   values (:symbol, :found_in, :depends_on)'''
        ]
        self.execute(add_dependency, {'symbol': symbol.name,
                                      'found_in': str(symbol.found_in),
                                      'depends_on': depends_on})

    def remove_c_file(self, filename: Union[Path, str]) -> None:
        """
        Removes all records relating of a particular source file.
        :param filename: File to be removed.
        """
        remove_file = [
            '''delete from c_prerequisite
               where found_in = :filename''',
            '''delete from c_symbol where found_in=:filename'''
            ]
        self.execute(remove_file, {'filename': str(filename)})

    def get_symbol(self, name: str) -> List[CInfo]:
        """
        Gets the details of symbols given their name.
        It is possible that identically named symbols appear in multiple
        files, hence why a list is returned. It would be an error to try
        linking these into a single executable but that is not a concern for
        the model of the source tree.
        :param name: symbol name.
        :return: List of symbol information objects.
        """
        query = '''select s.symbol, s.found_in, p.prerequisite
                   from c_symbol as s
                   left join c_prerequisite as p
                   on p.symbol = s.symbol and p.found_in = s.found_in
                   where s.symbol=:symbol
                   order by s.symbol, s.found_in, p.prerequisite'''
        rows = self.execute(query, {'symbol': name})
        info_list: List[CInfo] = []
        previous_id = None
        info: Optional[CInfo] = None
        for row in rows:
            symbol_id = CSymbolID(row['symbol'], Path(row['found_in']))
            if previous_id is not None and symbol_id == previous_id:
                if info is not None:
                    info.add_prerequisite(row['prerequisite'])
            else:  # symbol_id != previous_id
                if info is not None:
                    info_list.append(info)
                info = CInfo(symbol_id)
                if row['prerequisite'] is not None:
                    info.add_prerequisite((row['prerequisite']))
                previous_id = symbol_id
        if info is not None:  # We have left overs
            info_list.append(info)
        if len(info_list) == 0:
            message = 'symbol "{symbol}" not found in database.'
            raise WorkingStateException(message.format(symbol=name))
        return info_list

    def depends_on(self, symbol: CSymbolID)\
            -> Generator[CSymbolID, None, None]:
        """
        Gets the prerequisite symbols of a symbol.
        :param symbol: symbol identifier.
        :return: Prerequisite symbol names. May be an empty list.
        """
        query = '''select p.prerequisite, f.found_in
                   from c_prerequisite as p
                   left join c_symbol as f on f.symbol = p.prerequisite
                   where p.symbol=:symbol and p.found_in=:filename
                   order by p.symbol, f.found_in'''
        rows = self.execute(query, {'symbol': symbol.name,
                                    'filename': str(symbol.found_in)})
        for row in rows:
            if row['found_in'] is None:
                yield CSymbolUnresolvedID(row['prerequisite'])
            else:  # row['found_in'] is not None
                yield CSymbolID(row['prerequisite'], Path(row['found_in']))


class CAnalyser(Task):
    def __init__(self):
        # self.database = SqliteStateDatabase(workspace)
        self.verbose = False

    def _locate_include_regions(self, trans_unit) -> None:
        # Aim is to identify where included (top level) regions
        # start and end in the file
        self._include_region = []

        # Use a deque to implement a rolling window of 4 identifiers
        # (enough to be sure we can spot an entire pragma)
        identifiers: deque = deque([])
        for token in trans_unit.cursor.get_tokens():
            identifiers.append(token)
            if len(identifiers) < 4:
                continue
            if len(identifiers) > 4:
                identifiers.popleft()

            # Trigger off of the FAB identifier only to save
            # on joining the group too frequently
            if identifiers[2].spelling == "FAB":
                lineno = identifiers[2].location.line
                full = " ".join(id.spelling for id in identifiers)
                if full == "# pragma FAB SysIncludeStart":
                    self._include_region.append(
                        (lineno, "sys_include_start"))
                elif full == "# pragma FAB SysIncludeEnd":
                    self._include_region.append(
                        (lineno, "sys_include_end"))
                elif full == "# pragma FAB UsrIncludeStart":
                    self._include_region.append(
                        (lineno, "usr_include_start"))
                elif full == "# pragma FAB UsrIncludeEnd":
                    self._include_region.append(
                        (lineno, "usr_include_end"))

    def _check_for_include(self, lineno) -> Optional[str]:
        # Check whether a given line number is in a region that
        # has come from an include (and return what kind of include)
        include_stack = []
        for region_line, region_type in self._include_region:
            if region_line > lineno:
                break
            if region_type.endswith("start"):
                include_stack.append(region_type.replace("_start", ""))
            elif region_type.endswith("end"):
                include_stack.pop()
        if include_stack:
            return include_stack[-1]
        else:
            return None

    def run(self, hashed_file: HashedFile):
        fpath, file_hash = hashed_file
        logger = logging.getLogger(__name__)
        log_or_dot(logger, f"analysing {fpath}")

        reader = FileTextReader(fpath)

        af = AnalysedFile(fpath=fpath, file_hash=file_hash)

        index = clang.cindex.Index.create()
        translation_unit = index.parse(reader.filename,
                                       args=["-xc"])

        # Create include region line mappings
        self._locate_include_regions(translation_unit)

        # Now walk the actual nodes and find all relevant external symbols
        usr_symbols = []

        # current_def = None
        for node in translation_unit.cursor.walk_preorder():
            if not node.spelling:
                continue

            # ignore sys include stuff
            if self._check_for_include(node.location.line) == "sys_include":
                continue

            if self.verbose:
                logger.debug('Considering node: %s', node.spelling)

            if node.kind in {clang.cindex.CursorKind.FUNCTION_DECL, clang.cindex.CursorKind.VAR_DECL}:
                if self.verbose:
                    logger.debug('  * Is a declaration')
                if node.is_definition():
                    # only global symbols can be used by other files, not static symbols
                    if node.linkage == clang.cindex.LinkageKind.EXTERNAL:
                        # This should catch function definitions which are exposed
                        # to the rest of the application
                        if self.verbose:
                            logger.debug('  * Is defined in this file')
                        # todo: ignore if inside user pragmas?
                        af.add_symbol_def(node.spelling)
                else:
                    # Any other declarations should be coming in via headers,
                    # we can use the injected pragmas to work out whether these
                    # are coming from system headers or user headers
                    if self._check_for_include(node.location.line) == "usr_include":
                        if self.verbose:
                            logger.debug('  * Is not defined in this file')
                        usr_symbols.append(node.spelling)

            elif node.kind in {clang.cindex.CursorKind.CALL_EXPR, clang.cindex.CursorKind.DECL_REF_EXPR}:
                # When encountering a function call we should be able to
                # cross-reference it with a definition seen earlier; and
                # if it came from a user supplied header then we will
                # consider it a dependency within the project
                if self.verbose:
                    logger.debug('  * Is a symbol usage')
                if node.spelling in usr_symbols:
                    if self.verbose:
                        logger.debug('  * Is a user symbol (so a dependency)')
                    af.add_symbol_dep(node.spelling)

        return af


def _CTextReaderPragmas(fpath):
    """
    Reads a C source file but when encountering an #include
    preprocessor directive injects a special Fab-specific
    #pragma which can be picked up later by the Analyser
    after the preprocessing
    """

    _include_re: str = r'^\s*#include\s+(\S+)'
    _include_pattern: Pattern = re.compile(_include_re)

    for line in open(fpath, 'rt', encoding='utf-8'):
        include_match: Optional[Match]  = _include_pattern.match(line)
        if include_match:
            # For valid C the first character of the matched
            # part of the group will indicate whether this is
            # a system library include or a user include
            include: str = include_match.group(1)
            # TODO: Is this sufficient?  Or do the pragmas
            #       need to include identifying info
            #       e.g. the name of the original include?
            # TODO: DO we need to mark system includes?
            if include.startswith('<'):
                yield '#pragma FAB SysIncludeStart\n'
                yield line
                yield '#pragma FAB SysIncludeEnd\n'
            elif include.startswith(('"', "'")):
                yield '#pragma FAB UsrIncludeStart\n'
                yield line
                yield '#pragma FAB UsrIncludeEnd\n'
            else:
                msg = 'Found badly formatted #include'
                raise TaskException(msg)
        else:
            yield line


# def CPragmaInjector(fpath: Path):
#
#     # todo: error handling
#     logger = logging.getLogger(__name__)
#     logger.debug('Injecting pragmas into: %s', fpath)
#
#     tmp_output_fpath = fpath.parent / (fpath.name + ".prag")
#     tmp_output_fpath.open('w').writelines(_CTextReaderPragmas(fpath))
#
#     shutil.move(tmp_output_fpath, fpath)
#     return fpath


class CPreProcessor(Task):
    """Used for both C and Fortran"""

    def __init__(self,
                 preprocessor: List[str],
                 flags: FlagsConfig,
                 workspace: Path,
                 output_suffix=".c",  # but is also used for fortran
                 debug_skip=False,
                 ):
        self._preprocessor = preprocessor
        self._flags = flags
        self._workspace = workspace
        self.output_suffix = output_suffix
        self.debug_skip = debug_skip

    def run(self, fpath: Path):
        logger = logging.getLogger(__name__)

        output_fpath = input_to_output_fpath(workspace=self._workspace, input_path=fpath)

        if fpath.suffix == ".c":
            # pragma injection
            prag_output_fpath = fpath.parent / (fpath.name + ".prag")
            prag_output_fpath.open('w').writelines(_CTextReaderPragmas(fpath))
            input_fpath = prag_output_fpath
        elif fpath.suffix in [".f90", ".F90"]:
            input_fpath = fpath
            output_fpath = output_fpath.with_suffix('.f90')
        else:
            raise ValueError(f"Unexpected file type: '{str(fpath)}'")

        # for dev speed, but this could become a good time saver with, e.g, hashes or something
        if self.debug_skip and output_fpath.exists():
            log_or_dot(logger, f'Preprocessor skipping: {fpath}')
            return output_fpath

        if not output_fpath.parent.exists():
            output_fpath.parent.mkdir(parents=True, exist_ok=True)

        command = [*self._preprocessor]
        command.extend(self._flags.flags_for_path(fpath))

        # the flags we were given might contain include folders which need to be converted into absolute paths
        fixup_command_includes(command=command, source_root=self._workspace / BUILD_SOURCE, file_path=fpath)

        # input and output files
        command.append(str(input_fpath))
        command.append(str(output_fpath))

        log_or_dot(logger, 'Preprocessor running command: ' + ' '.join(command))
        try:
            subprocess.run(command, check=True, capture_output=True)
        except subprocess.CalledProcessError as err:
            return Exception(f"Error running preprocessor command: {command}\n{err.stderr}")

        return output_fpath


class CCompiler(Task):

    def __init__(self,
                 compiler: List[str],
                 # flags: List[str],
                 flags: FlagsConfig,
                 workspace: Path):
        self._compiler = compiler
        self._flags = flags
        self._workspace = workspace

    def run(self, af: AnalysedFile):
        logger = logging.getLogger(__name__)

        command = self._compiler
        # command.extend(self._flags)
        command.extend(self._flags.flags_for_path(af.fpath))
        command.append(str(af.fpath))

        output_file = (self._workspace / af.fpath.with_suffix('.o').name)
        command.extend(['-o', str(output_file)])

        logger.debug('Running command: ' + ' '.join(command))

        try:
            res = subprocess.run(command, check=True)
            if res.returncode != 0:
                # todo: specific exception
                return Exception(f"The compiler exited with non zero: {res.stderr.decode()}")
        except Exception as err:
            return Exception(f"error compiling {af.fpath}: {err}")

        # object_artifact = Artifact(output_file, BinaryObject, Compiled)
        # for definition in artifact.defines:
        #     object_artifact.add_definition(definition)

        # return [object_artifact]

        return CompiledFile(af, output_file)
