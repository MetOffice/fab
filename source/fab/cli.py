# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, Optional

import fab
from fab.artefacts import CollectionGetter
from fab.build_config import BuildConfig
from fab.constants import PRAGMAD_C
from fab.steps.analyse import Analyse
from fab.steps.c_pragma_injector import CPragmaInjector
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran, get_fortran_compiler, get_fortran_preprocessor
from fab.steps.find_source_files import FindSourceFiles
from fab.steps.grab.folder import GrabFolder
from fab.steps.link import LinkExe
from fab.steps.preprocess import preprocess_c, preprocess_fortran
from fab.steps.root_inc_files import RootIncFiles


def _generic_build_config(folder: Path, kwargs: Optional[Dict] = None) -> BuildConfig:
    folder = folder.resolve()
    kwargs = kwargs or {}

    # Within the fab workspace, we'll create a project workspace.
    # Ideally we'd just use folder.name, but to avoid clashes, we'll use the full absolute path.
    label = '/'.join(folder.parts[1:])

    fpp, fpp_flags = get_fortran_preprocessor()
    fc, fc_flags = get_fortran_compiler()

    # linker and flags depend on compiler
    linkers = {
        'gfortran': ('gcc', ['-lgfortran']),
        # 'ifort': (..., [...])
    }
    try:
        linker, linker_flags = linkers[fc]
    except KeyError:
        raise NotImplementedError(f"Fab's zero configuration mode does not yet work with compiler '{fc}'")

    config = BuildConfig(
        project_label=label,
        steps=[
            GrabFolder(folder),
            FindSourceFiles(),

            RootIncFiles(),  # JULES helper, get rid of this eventually

            preprocess_fortran(preprocessor=fpp, common_flags=fpp_flags),

            CPragmaInjector(),
            preprocess_c(source=CollectionGetter(PRAGMAD_C)),

            Analyse(find_programs=True),

            CompileFortran(compiler=fc, common_flags=fc_flags),
            CompileC(),

            LinkExe(linker=linker, flags=linker_flags),
        ],
        **kwargs,
    )

    return config


def cli_fab():
    """
    Running Fab from the command line will attempt to build the project in the current or given folder.

    """
    arg_parser = ArgumentParser()
    arg_parser.add_argument('folder', nargs='?', default='.', type=Path)
    arg_parser.add_argument('--version', action='version', version=f'%(prog)s {fab.__version__}')
    args = arg_parser.parse_args()

    config = _generic_build_config(args.folder)

    config.run()
