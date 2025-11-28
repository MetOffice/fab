# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''This module tests if the Fortran analyser handles contained subroutines and
subroutines in the same module - none of which should be listed as external
dependency.
'''

from pathlib import Path

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps.analyse import analyse
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files
from fab.steps.grab.folder import grab_folder
from fab.steps.link import link_exe
from fab.tools.category import Category
from fab.tools.tool_box import ToolBox
from fab.tools.tool_repository import ToolRepository


PROJECT_SOURCE = Path(__file__).parent / 'test_contained_subroutine'


def test_contained_subroutine(tmp_path):
    '''The test_contained_subroutine directory contains two main programs, one
    called `main`, one `contained`. The first one uses `mod_with_contain`,
    which calls a `contained` subroutine `contained`. This test makes sure
    that:
    1. the main program `contained` is not linked in (otherwise we get
        duplicated main symbols defined at link time)
    2. the `contained` subroutine `contained` is indeed not listed as a
        dependency
    '''

    tb = ToolBox()
    compiler = tb.get_tool(Category.FORTRAN_COMPILER, mpi=False, openmp=False)
    tr = ToolRepository()
    # Make sure we get a Fortran linker, by using the Fortran compiler as base:
    linker = tr.get_tool(Category.LINKER, f"linker-{compiler.name}")
    tb.add_tool(linker)

    with BuildConfig(fab_workspace=tmp_path, tool_box=tb,
                     project_label='contained_subroutine',
                     multiprocessing=False) as config:
        grab_folder(config, PROJECT_SOURCE)
        find_source_files(config)
        analyse(config, root_symbol='main')
        build_tree = config.artefact_store[ArtefactSet.BUILD_TREES]["main"]

        af_mod_with_contain = None
        for file_name in build_tree:
            if "mod_with_contain" in str(file_name):
                af_mod_with_contain = build_tree[file_name]
                break

        # The module should not contain any dependencies, the dependency to
        # `contained` is resolved from the subroutine it contains.
        assert af_mod_with_contain.symbol_deps == set()

        # Just in case, also compile and link
        compile_fortran(config)
        link_exe(config)
