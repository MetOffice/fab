# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import subprocess
from pathlib import Path

from fab.build_config import BuildConfig
from fab.constants import EXECUTABLES
from fab.steps.analyse import analyse
from fab.steps.c_pragma_injector import c_pragma_injector
from fab.steps.compile_c import compile_c
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files
from fab.steps.grab.folder import grab_folder
from fab.steps.link import link_exe
from fab.steps.preprocess import preprocess_fortran, preprocess_c

import pytest

PROJECT_SOURCE = Path(__file__).parent / 'project-source'


def test_CFortranInterop(tmp_path):

    # build
    with BuildConfig(fab_workspace=tmp_path, project_label='foo', multiprocessing=False) as config, \
         pytest.warns(UserWarning, match="removing managed flag"):

        grab_folder(config, src=PROJECT_SOURCE),
        find_source_files(config),

        c_pragma_injector(config),
        preprocess_c(config),
        preprocess_fortran(config),

        analyse(config, root_symbol='main'),

        compile_c(config, common_flags=['-c', '-std=c99']),
        compile_fortran(config, common_flags=['-c']),
        link_exe(config, linker='gcc', flags=['-lgfortran']),
        # todo: on an ubuntu vm, we needed these before the object files - investigate further
        # [
        #     '/lib/x86_64-linux-gnu/libc.so.6',
        #     '/lib/x86_64-linux-gnu/libgfortran.so.5',
        # ]

    assert len(config._artefact_store[EXECUTABLES]) == 1

    # run
    command = [str(config._artefact_store[EXECUTABLES][0])]
    res = subprocess.run(command, capture_output=True)
    output = res.stdout.decode()
    assert output == ''.join(open(PROJECT_SOURCE / 'expected.exec.txt').readlines())
