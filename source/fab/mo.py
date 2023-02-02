# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
A temporary place for some Met Office specific logic which, for now, needs to be integrated into Fab's internals.

"""

from pathlib import Path
from typing import Dict, List

from fab.dep_tree import AnalysedDependent, filter_source_tree, logger
from fab.parse.c import AnalysedC
from fab.parse.fortran import AnalysedFortran


def add_mo_commented_file_deps(source_tree: Dict[Path, AnalysedDependent]):
    """
    Handle dependencies from Met Office "DEPENDS ON:" code comments which refer to a c file.
    These are the comments which refer to a .o file and not those which just refer to symbols.

    :param source_tree:
        The source tree of analysed files.

    """
    # todo: this would be better if filtered by type, i,e, AnalysedFortran & AnalysedC
    analysed_fortran: List[AnalysedFortran] = filter_source_tree(source_tree, '.f90')  # type: ignore
    analysed_c: List[AnalysedC] = filter_source_tree(source_tree, '.c')  # type: ignore

    lookup = {c.fpath.name: c for c in analysed_c}
    num_found = 0
    for f in analysed_fortran:
        num_found += len(f.mo_commented_file_deps)
        for dep in f.mo_commented_file_deps:
            f.file_deps.add(lookup[dep].fpath)
    logger.info(f"processed {num_found} DEPENDS ON file dependencies")
