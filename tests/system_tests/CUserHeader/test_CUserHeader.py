# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import subprocess
from pathlib import Path

from pytest import importorskip

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps.analyse import analyse
from fab.steps.c_pragma_injector import c_pragma_injector
from fab.steps.compile_c import compile_c
from fab.steps.find_source_files import find_source_files
from fab.steps.grab.folder import grab_folder
from fab.steps.link import link_exe
from fab.steps.preprocess import preprocess_c
from fab.tools.tool_box import ToolBox

clang = importorskip('clang', reason="Clang bindings not found.")

PROJECT_SOURCE = Path(__file__).parent / 'project-source'


def test_CUseHeader(tmp_path):

    # build
    with BuildConfig(fab_workspace=tmp_path, tool_box=ToolBox(),
                     project_label='foo', multiprocessing=False) as config:

        grab_folder(config, PROJECT_SOURCE)
        find_source_files(config)
        c_pragma_injector(config)
        preprocess_c(config)
        analyse(config, root_symbol='main')
        compile_c(config, common_flags=['-c', '-std=c99'])
        link_exe(config, flags=['-lgfortran'])

    assert len(config.artefact_store[ArtefactSet.EXECUTABLES]) == 1

    # run
    command = [str(list(config.artefact_store[ArtefactSet.EXECUTABLES])[0])]
    res = subprocess.run(command, capture_output=True)
    output = res.stdout.decode()
    assert output == ''.join(open(PROJECT_SOURCE / 'expected.exec.txt').readlines())
