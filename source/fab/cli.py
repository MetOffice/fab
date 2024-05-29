# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''Functions to run Fab from the command line.
'''

import sys
from pathlib import Path
from typing import Dict, Optional

from fab.steps.analyse import analyse
from fab.steps.c_pragma_injector import c_pragma_injector
from fab.steps.compile_c import compile_c
from fab.steps.link import link_exe
from fab.steps.root_inc_files import root_inc_files
from fab.artefacts import CollectionGetter
from fab.build_config import BuildConfig
from fab.constants import PRAGMAD_C
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files
from fab.steps.grab.folder import grab_folder
from fab.steps.preprocess import preprocess_c, preprocess_fortran
from fab.tools import Categories, ToolBox, ToolRepository
from fab.util import common_arg_parser


def _generic_build_config(folder: Path, kwargs=None) -> BuildConfig:
    project_label = 'zero_config_build'
    if kwargs:
        project_label = kwargs.pop('project_label', 'zero_config_build') or project_label

    # Set the default Fortran compiler as linker (otherwise e.g. the
    # C compiler might be used in linking, requiring additional flags)
    tr = ToolRepository()
    fc = tr.get_default(Categories.FORTRAN_COMPILER)
    # TODO: This assumes a mapping of compiler name to the corresponding
    # linker name (i.e. `linker-gfortran` or `linker-ifort`). Still, that's
    # better than hard-coding gnu here.
    linker = tr.get_tool(Categories.LINKER, f"linker-{fc.name}")
    tool_box = ToolBox()
    tool_box.add_tool(fc)
    tool_box.add_tool(linker)
    # Within the fab workspace, we'll create a project workspace.
    # Ideally we'd just use folder.name, but to avoid clashes, we'll use the full absolute path.
    with BuildConfig(project_label=project_label,
                     tool_box=tool_box, **kwargs) as config:
        grab_folder(config, folder)
        find_source_files(config)
        root_inc_files(config)  # JULES helper, get rid of this eventually
        preprocess_fortran(config)
        c_pragma_injector(config)
        preprocess_c(config, source=CollectionGetter(PRAGMAD_C))
        analyse(config, find_programs=True)
        compile_fortran(config)
        compile_c(config)
        # If ifort should be used, it might need the flag `-nofor-main` in
        # case of a mixed language compilation (main program in C, linking
        # with ifort).
        link_exe(config, flags=[])

    return config


def cli_fab(folder: Optional[Path] = None, kwargs: Optional[Dict] = None):
    """
    Running Fab from the command line will attempt to build the project in the current or
    given folder. The following params are used for testing. When run normally any parameters
    will be caught by a common_arg_parser.

    :param folder:
        source folder (Testing Only)
    :param kwargs:
        parameters  ( Testing Only )

    """
    kwargs = kwargs or {}

    # We check if 'fab' was called directly. As it can be called by other things like 'pytest',
    # the cli arguments may not apply to 'fab' which will cause arg_parser to fail with an
    # invalid argument message.
    if Path(sys.argv[0]).parts[-1] == 'fab':
        arg_parser = common_arg_parser()
        kwargs = vars(arg_parser.parse_args())
        _folder = kwargs.pop('folder')
    else:
        # Required when testing
        assert folder is not None
        _folder = folder

    config = _generic_build_config(_folder, kwargs)
    return config
