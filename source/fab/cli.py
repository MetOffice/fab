# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, Optional

from fab.artefacts import CollectionGetter
from fab.build_config import BuildConfig
from fab.constants import PRAGMAD_C
from fab.steps.analyse import Analyse
from fab.steps.c_pragma_injector import CPragmaInjector
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran, get_fortran_compiler
from fab.steps.find_source_files import FindSourceFiles
from fab.steps.grab.folder import GrabFolder
from fab.steps.link import LinkExe
from fab.steps.preprocess import c_preprocessor, fortran_preprocessor
from fab.steps.root_inc_files import RootIncFiles


def _generic_build_config(folder: Path, kwargs: Optional[Dict] = None) -> BuildConfig:
    folder = folder.resolve()
    kwargs = kwargs or {}

    # Within the fab workspace, we'll create a project workspace.
    # Ideally we'd just use folder.name, but to avoid clashes, we'll use the full absolute path.
    label = '/'.join(folder.parts[1:])

    # which compiler is set in the environment?
    # we need to know because there are some linker flags that we'll need
    compiler = get_fortran_compiler()[0]
    if compiler == 'gfortran':
        link_step = LinkExe(linker='gcc', flags=['-lgfortran'])
    else:
        raise NotImplementedError(f"Fab's zero config not yet configured for your compiler: '{compiler}'")

    config = BuildConfig(
        project_label=label,
        steps=[
            GrabFolder(folder),
            FindSourceFiles(),

            RootIncFiles(),  # JULES helper, get rid of this eventually

            fortran_preprocessor(common_flags=['-P']),

            CPragmaInjector(),
            c_preprocessor(source=CollectionGetter(PRAGMAD_C)),

            Analyse(find_programs=True),

            CompileFortran(),
            CompileC(),

            link_step,
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
    args = arg_parser.parse_args()

    config = _generic_build_config(args.folder)

    config.run()
