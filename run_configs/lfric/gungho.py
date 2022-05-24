#!/usr/bin/env python3
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import logging
import os
import shutil
from pathlib import Path

from fab.steps.archive_objects import ArchiveObjects
from typing import Dict

from fab.artefacts import SuffixFilter
from fab.steps.link_exe import LinkExe

from fab.steps.compile_fortran import CompileFortran

from fab.steps.analyse import Analyse

from fab.constants import BUILD_OUTPUT

from fab.build_config import BuildConfig
from fab.steps import Step
from fab.steps.grab import GrabFolder
from fab.steps.preprocess import PreProcessor, fortran_preprocessor
from fab.steps.walk_source import FindSourceFiles
from fab.util import run_command, log_or_dot, by_type, input_to_output_fpath, check_for_errors
from grab_lfric import lfric_source, gpl_utils_source

logger = logging.getLogger('fab')


# todo: optimisation path stuff

# todo: what does "don't build the _psy.f90s until the kernel files exist, but don't worry if it's updated" mean?
#       re the | $(KERNEL_SOURCE) in psyclone.mk


def gungho():

    config = BuildConfig(
        project_label='gungho',  # same project label as the grab script, => same project workspace
        # multiprocessing=False,
        reuse_artefacts=True
    )

    lfric_source_config = lfric_source()
    config.steps = [

        GrabFolder(src=lfric_source_config.source_root / 'lfric/infrastructure/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/components/driver/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/components/science/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/components/lfric-xios/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/gungho/source/', dst_label=''),

        # This wasn't in the makefiles but get_Pnm_star_kernel_mod is imported by physical_op_constants_mod_psy.f90.
        # It's not yet clear to us how the makefiles get this.
        GrabFolder(src=lfric_source_config.source_root / 'lfric/um_physics/source/kernel/stph/', dst_label='um_physics/source/kernel/stph/'),

        # also missing, also not yet sure how the makefiles get this
        GrabFolder(src=lfric_source_config.source_root / 'lfric/um_physics/source/constants/', dst_label='um_physics/source/constants'),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/lfric_atm/source/constants/', dst_label='lfric_atm/source/constants'),

        # generate more source files in source and source/configuration
        Configurator(
            lfric_source=lfric_source_config.source_root / 'lfric',
            gpl_utils_source=gpl_utils_source().source_root / 'gpl_utils'),

        FindSourceFiles(file_filtering=[
            # todo: allow a single string
            (['unit-test', '/test/'], False),
        ]),

        fortran_preprocessor(
            # preprocessor='cpp',
            preprocessor='cpp -traditional-cpp',
            common_flags=['-P'],
        ),

        psyclone_preprocessor(),

        PsyThing(kernel_roots=[
            config.project_workspace / BUILD_OUTPUT,
            # config.project_workspace / '../lfric-source/source/lfric/um_physics/source/kernel/stph',
        ]),

        # psyclone_preprocessor(),

        # Configurator(
        #     lfric_source=lfric_source_config.source_root / 'lfric',
        #     gpl_utils_source=gpl_utils_source().source_root / 'gpl_utils'),

        FparserWorkaround_StopConcatenation(name='fparser stop bug workaround'),

        Analyse(
            root_symbol='gungho',
            ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        ),

        CompileFortran(
            # compiler='mpifort',
            compiler=os.getenv('FC', 'gfortran'),
            common_flags=[
                '-c', '-J', '$output',
                # '-I' + os.path.expanduser('~/.conda/envs/sci-fab/lib'),
            ]),

        ArchiveObjects(output_fpath='$output/objects.a'),

        LinkExe(
            # linker='gfortran',
            linker='mpifort',
            output_fpath=config.project_workspace / 'gungho.exe',
            flags=[

                # EXTERNAL_DYNAMIC_LIBRARIES
                '-lyaxt', '-lyaxt_c', '-lnetcdff', '-lnetcdf', '-lhdf5',

                # EXTERNAL_STATIC_LIBRARIES
                '-lxios',

                '-lstdc++',
            ],

        ),

    ]

    return config


class Configurator(Step):

    def __init__(self, lfric_source, gpl_utils_source):
        super().__init__(name='configurator thing')
        self.lfric_source: Path = lfric_source
        self.gpl_utils_source: Path = gpl_utils_source

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store=artefact_store, config=config)

        rose_picker_tool = self.gpl_utils_source / 'rose_picker/rose_picker'
        gen_namelist_tool = self.lfric_source / 'infrastructure/build/tools/GenerateNamelist'
        gen_loader_tool = self.lfric_source / 'infrastructure/build/tools/GenerateLoader'
        gen_feigns_tool = self.lfric_source / 'infrastructure/build/tools/GenerateFeigns'

        config_dir = config.source_root / 'configuration'

        env = os.environ
        rose_lfric_path = self.gpl_utils_source / 'lib/python'
        env['PYTHONPATH'] += f':{rose_lfric_path}'

        # "rose picker"
        # creates rose-meta.json and config_namelists.txt in gungho/source/configuration
        rose_meta_conf = self.lfric_source / 'gungho/rose-meta/lfric-gungho/HEAD/rose-meta.conf'
        logger.info('rose_picker')
        run_command(
            command=[
                str(rose_picker_tool), str(rose_meta_conf),
                '-directory', str(config_dir),
                '-include_dirs', self.lfric_source],
            env=env,
        )

        # "build_config_loaders"
        # builds a bunch of f90s from the json
        logger.info('GenerateNamelist')
        run_command(
            command=[
                str(gen_namelist_tool),
                '-verbose',
                str(config_dir / 'rose-meta.json'),
                '-directory', str(config_dir),
                # '--norandom_enums'
            ]
        )

        # create configuration_mod.f90 in source root
        logger.info('GenerateLoader')
        names = [name.strip() for name in open(config_dir / 'config_namelists.txt').readlines()]
        configuration_mod_fpath = config.source_root / 'configuration_mod.f90'
        run_command(
            command=[
                str(gen_loader_tool),
                configuration_mod_fpath,
                *names,
            ]
        )

        # create feign_config_mod.f90 in source root
        logger.info('GenerateFeigns')
        feign_config_mod_fpath = config.source_root / 'feign_config_mod.f90'
        run_command(
            command=[
                str(gen_feigns_tool),
                str(config_dir / 'rose-meta.json'),
                '-output', feign_config_mod_fpath,
            ]
        )

        # put the generated source into an artefact
        artefact_store['configurator_output'] = [
            configuration_mod_fpath,
            feign_config_mod_fpath
        ]


class FparserWorkaround_StopConcatenation(Step):
    """
    fparser can't handle string concat in a stop statement. This step is a workaround.

    https://github.com/stfc/fparser/issues/330

    """
    def run(self, artefact_store, config):
        feign_config_mod_fpath = config.source_root / 'feign_config_mod.f90'

        # rename "broken" version
        broken_version = feign_config_mod_fpath.with_suffix('.broken')
        shutil.move(feign_config_mod_fpath, broken_version)

        # make fixed version
        bad = "_config: '// &\n        'Unable to close temporary file'"
        good = "_config: Unable to close temporary file'"

        open(feign_config_mod_fpath, 'wt').write(
            open(broken_version, 'rt').read().replace(bad, good))


def psyclone_preprocessor():
    return PreProcessor(
        preprocessor='cpp -traditional-cpp',

        # source=SuffixFilter('psyclone_output', '.F90'),
        # output_collection='preprocessed_psyclone',

        source=SuffixFilter('all_source', '.x90'),
        output_collection='preprocessed_x90',

        output_suffix='.x90',
        name='preprocess x90',
        common_flags=['-P'],
    )


class PsyThing(Step):

    def __init__(self, name=None, kernel_roots=None):
        super().__init__(name=name or 'psy thingy')
        self.kernel_roots = kernel_roots or []

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store=artefact_store, config=config)

        results = self.run_mp(artefact_store['preprocessed_x90'], self.do_one_file)
        # x90s = SuffixFilter('all_source', '.x90')(artefact_store)
        # results = self.run_mp(x90s, self.do_one_file)

        check_for_errors(results, caller_label=self.name)

        successes = list(filter(lambda r: not isinstance(r, Exception), results))
        logger.info(f"success with {len(successes)} files")
        artefact_store['psyclone_output'] = []
        for files in successes:
            artefact_store['psyclone_output'].extend(files)

    def do_one_file(self, x90_file):
        log_or_dot(logger=logger, msg=str(x90_file))
        # logger.info(f'psycloning {x90_file}')

        generated = x90_file.parent / (str(x90_file.stem) + '_psy.f90')
        modified_alg = x90_file.with_suffix('.f90')

        # generate into the build output, not the source
        generated = input_to_output_fpath(
            source_root=self._config.source_root, project_workspace=self._config.project_workspace, input_path=generated)
        modified_alg = input_to_output_fpath(
            source_root=self._config.source_root, project_workspace=self._config.project_workspace, input_path=modified_alg)
        generated.parent.mkdir(parents=True, exist_ok=True)

        # -d specifies "a root directory structure containing kernel source"
        kernel_options = sum([['-d', k] for k in self.kernel_roots], [])

        command = [
            'psyclone', '-api', 'dynamo0.3',
            '-l', 'all',
            *kernel_options,
            '-opsy', generated,  # filename of generated PSy code
            '-oalg', modified_alg,  # filename of transformed algorithm code
            x90_file,
        ]

        if self._config.reuse_artefacts and Path(modified_alg).exists():
            # logger.info(f'PsyThing skipping {x90_file}')
            pass
        else:
            try:
                run_command(command)
            except Exception as err:
                logger.error(err)
                return err

        result = [modified_alg]
        if Path(generated).exists():
            result.append(generated)
        return result


if __name__ == '__main__':
    # logger.setLevel(logging.DEBUG)

    gungho_config = gungho()
    gungho_config.run()
