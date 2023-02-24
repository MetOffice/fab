# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
"""
C language handling classes.

"""
import logging
import warnings
from collections import deque
from pathlib import Path
from typing import List, Optional, Union, Tuple

from fab.dep_tree import AnalysedDependent

try:
    import clang  # type: ignore
    import clang.cindex  # type: ignore
except ImportError:
    clang = None

from fab.util import log_or_dot, file_checksum

logger = logging.getLogger(__name__)


class AnalysedC(AnalysedDependent):
    """
    An analysis result for a single C file, containing symbol definitions and dependencies.

    Note: We don't need to worry about compile order with pure C projects; we can compile all in one go.
          However, with a *Fortran -> C -> Fortran* dependency chain, we do need to ensure that one Fortran file
          is compiled before another, so this class must be part of the dependency tree analysis.

    """
    # Note: This subclass adds nothing to it's parent, which provides everything it needs.
    #       We'd normally remove an irrelevant class like this but we want to keep the door open
    #       for filtering analysis results by type, rather than suffix.
    pass


class CAnalyser(object):
    """
    Identify symbol definitions and dependencies in a C file.

    """

    def __init__(self):

        # runtime
        self._config = None

    # todo: simplifiy by passing in the file path instead of the analysed tokens?
    def _locate_include_regions(self, trans_unit) -> None:
        """
        Look for Fab pragmas identifying included code which came from system or user #includes.
        """
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
        """Check whether a given line number is in a region that has come from an include."""
        # todo: don't need a stack?
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

    def run(self, fpath: Path) \
            -> Union[Tuple[AnalysedC, Path], Tuple[Exception, None]]:

        if not clang:
            msg = 'clang not available, C analysis disabled'
            warnings.warn(msg, ImportWarning)
            return ImportWarning(msg), None

        # do we already have analysis results for this file?
        # todo: dupe - probably best in a parser base class
        file_hash = file_checksum(fpath).file_hash
        analysis_fpath = Path(self._config.prebuild_folder / f'{fpath.stem}.{file_hash}.an')
        if analysis_fpath.exists():
            log_or_dot(logger, f"found analysis prebuild for {fpath}")
            return AnalysedC.load(analysis_fpath), analysis_fpath

        log_or_dot(logger, f"analysing {fpath}")

        analysed_file = AnalysedC(fpath=fpath, file_hash=file_hash)

        # parse the file
        try:
            index = clang.cindex.Index.create()
            translation_unit = index.parse(fpath, args=["-xc"])
        except Exception as err:
            logger.exception(f'error parsing {fpath}')
            return err, None

        # Create include region line mappings
        try:
            self._locate_include_regions(translation_unit)
        except Exception as err:
            logger.exception(f'error locating include regions {fpath}')
            return err, None

        # Now walk the actual nodes and find all relevant external symbols
        try:
            usr_symbols: List[str] = []
            for node in translation_unit.cursor.walk_preorder():
                if not node.spelling:
                    continue
                # ignore sys include stuff
                if self._check_for_include(node.location.line) == "sys_include":
                    continue
                logger.debug('Considering node: %s', node.spelling)

                if node.kind in {clang.cindex.CursorKind.FUNCTION_DECL, clang.cindex.CursorKind.VAR_DECL}:
                    self._process_symbol_declaration(analysed_file, node, usr_symbols)
                elif node.kind in {clang.cindex.CursorKind.CALL_EXPR, clang.cindex.CursorKind.DECL_REF_EXPR}:
                    self._process_symbol_dependency(analysed_file, node, usr_symbols)
        except Exception as err:
            logger.exception(f'error walking parsed nodes {fpath}')
            return err, None

        analysed_file.save(analysis_fpath)
        return analysed_file, analysis_fpath

    def _process_symbol_declaration(self, analysed_file, node, usr_symbols):
        # Identify symbol declarations which are definitions or user includes
        logger.debug('  * Is a declaration')
        if node.is_definition():
            # only global symbols can be used by other files, not static symbols
            if node.linkage == clang.cindex.LinkageKind.EXTERNAL:
                # This should catch function definitions which are exposed to the rest of the application
                logger.debug('  * Is defined in this file')
                # todo: ignore if inside user pragmas?
                analysed_file.add_symbol_def(node.spelling)
        else:
            # Record any user included symbols in case they're referenced later in the code
            if self._check_for_include(node.location.line) == "usr_include":
                logger.debug('  * Is not defined in this file')
                usr_symbols.append(node.spelling)

    def _process_symbol_dependency(self, analysed_file, node, usr_symbols):
        # When encountering a function call we should be able to
        # cross-reference it with a definition seen earlier; and
        # if it came from a user supplied header then we will
        # consider it a dependency within the project

        logger.debug('  * Is a symbol usage')
        if node.spelling in usr_symbols:
            logger.debug('  * Is a user symbol (so a dependency)')
            analysed_file.add_symbol_dep(node.spelling)
