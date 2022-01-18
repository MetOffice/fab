# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
"""
C language handling classes.
"""
import logging
import subprocess
import re
import clang.cindex  # type: ignore
from collections import deque
from typing import \
    List, \
    Pattern, \
    Optional, \
    Match
from pathlib import Path

from fab.config_sketch import FlagsConfig
from fab.dep_tree import AnalysedFile

from fab.constants import BUILD_OUTPUT, BUILD_SOURCE

from fab.tasks import TaskException

from fab.util import log_or_dot, HashedFile, CompiledFile, fixup_command_includes, input_to_output_fpath


class CAnalyser(object):
    def __init__(self):
        self.verbose = False

    def _locate_include_regions(self, trans_unit) -> None:
        # Aim is to identify where included (top level) regions start and end in the file
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

        analysed_file = AnalysedFile(fpath=fpath, file_hash=file_hash)

        index = clang.cindex.Index.create()
        translation_unit = index.parse(fpath, args=["-xc"])

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
                        analysed_file.add_symbol_def(node.spelling)
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
                    analysed_file.add_symbol_dep(node.spelling)

        return analysed_file


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


class CPreProcessor(object):
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
        # todo: inconsistent with the compiler (and c?), which doesn't do this - discuss
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


class CCompiler(object):

    def __init__(self, compiler: List[str], flags: FlagsConfig, workspace: Path):
        self._compiler = compiler
        self._flags = flags
        self._workspace = workspace

    def run(self, af: AnalysedFile):
        logger = logging.getLogger(__name__)

        command = self._compiler
        command.extend(self._flags.flags_for_path(af.fpath))
        command.append(str(af.fpath))

        output_file = (self._workspace / BUILD_OUTPUT / af.fpath.with_suffix('.o').name)
        command.extend(['-o', str(output_file)])

        logger.debug('Running command: ' + ' '.join(command))

        try:
            res = subprocess.run(command, check=True)
            if res.returncode != 0:
                # todo: specific exception
                return Exception(f"The compiler exited with non zero: {res.stderr.decode()}")
        except Exception as err:
            return Exception(f"error compiling {af.fpath}: {err}")

        return CompiledFile(af, output_file)
