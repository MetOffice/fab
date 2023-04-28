# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
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
from fab.steps.compile_fortran import compile_fortran, get_fortran_compiler
from fab.steps.find_source_files import find_source_files
from fab.steps.grab.folder import grab_folder
from fab.steps.preprocess import preprocess_c, preprocess_fortran
from fab.util import common_arg_parser


def _generic_build_config(folder: Path, kwargs=None) -> BuildConfig:
    project_label = 'zero_config_build'
    if kwargs:
        project_label = kwargs.pop('project_label', 'zero_config_build') or project_label

    # Within the fab workspace, we'll create a project workspace.
    # Ideally we'd just use folder.name, but to avoid clashes, we'll use the full absolute path.
    linker, linker_flags = calc_linker_flags()
    with BuildConfig(project_label=project_label, **kwargs) as config:
        grab_folder(config, folder),
        find_source_files(config),

        root_inc_files(config),  # JULES helper, get rid of this eventually

        preprocess_fortran(config),

        c_pragma_injector(config),
        preprocess_c(config, source=CollectionGetter(PRAGMAD_C)),

        analyse(config, find_programs=True),

        compile_fortran(config),
        compile_c(config),

        link_exe(config, linker=linker, flags=linker_flags),

    return config


def calc_linker_flags():

    fc, _ = get_fortran_compiler()

    # linker and flags depend on compiler
    linkers = {
        'gfortran': ('gcc', ['-lgfortran']),
        # todo: test this and get it running
        # 'ifort': (..., [...])
    }
    try:
        linker, linker_flags = linkers[fc]
    except KeyError:
        raise NotImplementedError(f"Fab's zero configuration mode does not yet work with compiler '{fc}'")

    return linker, linker_flags


def cli_fab(folder: Path, kwargs: Optional[Dict] = None):
    """
    Running Fab from the command line will attempt to build the project in the current or given folder.
    The following params are used for testing. When run normally any parameters will be caught
    by a common_arg_parser.

    :param folder:
        source folder (Testing Only)
    :param kwargs:
        parameters  ( Testing Only )

    """
    kwargs = kwargs or {}
    if Path(sys.argv[0]).parts[-1] == 'fab':
        arg_parser = common_arg_parser()
        kwargs = vars(arg_parser.parse_args())

    folder = folder or kwargs.pop('folder', '.')

    config = _generic_build_config(folder, kwargs)
    return config
