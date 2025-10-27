# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
A temporary place for some Met Office specific logic which, for now, needs to
be integrated into Fab's internals.

"""

from pathlib import Path
from typing import Dict, Iterable, Optional

from fab.dep_tree import AnalysedDependent, logger
from fab.parse.c import AnalysedC
from fab.parse.fortran import AnalysedFortran


def add_mo_commented_file_deps(
       source_tree: Dict[Path, AnalysedDependent],
        ignore_dependencies: Optional[Iterable[str]] = None) -> None:
    """
    Handle dependencies from Met Office "DEPENDS ON:" code comments which
    refer to a c file. These are the comments which refer to a .o file and
    not those which just refer to symbols.

    :param source_tree:
        The source tree of analysed files.

    """
    ignore_set = set(ignore_dependencies) if ignore_dependencies else set()

    analysed_fortran = [i for i in source_tree.values()
                        if isinstance(i, AnalysedFortran)]
    analysed_c = [i for i in source_tree.values() if isinstance(i, AnalysedC)]

    lookup = {c.fpath.name: c for c in analysed_c}
    num_found = 0
    for f in analysed_fortran:
        num_found += len(f.mo_commented_file_deps)
        for dep in f.mo_commented_file_deps:
            if dep in ignore_set:
                continue
            # If the DEPENDS ON specified a .o file, rename it
            # to the expected c file.
            dep = dep.replace(".o", ".c")

            # Just in case, also allow that a .c file is specified in the
            # ignore list:
            if dep in ignore_set:
                continue

            if dep not in lookup:
                logger.error(f"DEPENDS ON dependency '{dep}' not found for "
                             f"file '{f.fpath}' - ignored for now, but "
                             f"the build might fail because of this.")
                continue
            f.file_deps.add(lookup[dep].fpath)
    logger.info(f"processed {num_found} DEPENDS ON file dependencies")
