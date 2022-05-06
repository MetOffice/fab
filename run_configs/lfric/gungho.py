import logging
import os
import shutil
from pathlib import Path
from typing import Dict

from fab.steps.link_exe import LinkExe

from fab.steps.compile_fortran import CompileFortran

from fab.steps.analyse import Analyse

from fab.constants import BUILD_OUTPUT

from fab.build_config import BuildConfig
from fab.steps import Step
from fab.steps.grab import GrabFolder
from fab.steps.preprocess import PreProcessor, fortran_preprocessor
from fab.steps.walk_source import FindSourceFiles
from fab.util import run_command, log_or_dot, FilterFpaths, by_type
from run_configs.lfric.grab import lfric_source, gpl_utils_source

logger = logging.getLogger('fab')


# todo: optimisation path stuff

# todo: what does "don't build the _psy.f90s until the kernel files exist, but don't worry if it's updated" mean?
#       re the | $(KERNEL_SOURCE) in psyclone.mk


def gungho():

    config = BuildConfig(
        project_label='gungho',  # same project label as the grab script, => same project workspace
        # multiprocessing=False,
        debug_skip=True
    )

    lfric_source_config = lfric_source()
    config.steps = [

        # todo: finickety with the slashes
        # GrabFolder(src=lfric_source_config.source_root / 'lfric/infrastructure/source/', dst_label='infrastructure/source'),
        # GrabFolder(src=lfric_source_config.source_root / 'lfric/components/driver/source/', dst_label='components/driver/source'),
        # GrabFolder(src=lfric_source_config.source_root / 'lfric/components/science/source/', dst_label='components/science/source'),
        # GrabFolder(src=lfric_source_config.source_root / 'lfric/components/lfric-xios/source/', dst_label='components/lfric-xios/source'),
        # GrabFolder(src=lfric_source_config.source_root / 'lfric/gungho/source/', dst_label='gungho/source'),

        GrabFolder(src=lfric_source_config.source_root / 'lfric/infrastructure/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/components/driver/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/components/science/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/components/lfric-xios/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/gungho/source/', dst_label=''),

        FindSourceFiles(file_filtering=[                                                # --> all_source
            # todo: allow a single string
            (['unit-test', '/test/'], False),
        ]),

        fortran_preprocessor(common_flags=['-P']),                                      # --> preprocessed_fortran

        PsyThing(kernel_roots=[
            config.project_workspace / BUILD_OUTPUT,
            config.project_workspace / '../lfric-source/source/lfric/um_physics/source/kernel/stph',
        ]),

        psyclone_preprocessor(),                                                        # --> preprocessed_psyclone

        Configurator(
            lfric_source=lfric_source_config.source_root / 'lfric',
            gpl_utils_source=gpl_utils_source().source_root / 'gpl_utils'),

        FparserWorkaround_StopConcatenation(name='fparser stop bug workaround'),

        Analyse(
            root_symbol='gungho',
            ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        ),

        CompileFortran(
            compiler='gfortran',
            # compiler='mpifort',
            common_flags=[
                '-c', '-J', '$output',
                '-I' + os.path.expanduser('~/.conda/envs/sci-fab/lib'),
            ]),

        LinkExe(linker='gfortran', output_fpath=config.project_workspace / 'gungho.exe'),

    ]

    return config


class Configurator(Step):

    def __init__(self, lfric_source, gpl_utils_source):
        super().__init__(name='configurator thing')
        self.lfric_source: Path = lfric_source
        self.gpl_utils_source: Path = gpl_utils_source

    def run(self, artefacts: Dict, config):
        super().run(artefacts=artefacts, config=config)

        # create rose-meta.json and config_namelists.txt in gungho/source/configuration
        working_dir = config.source_root
        config_dir = working_dir / 'configuration'

        env = os.environ
        rose_lfric_path = self.gpl_utils_source / 'lib/python'
        env['PYTHONPATH'] += f':{rose_lfric_path}'

        rose_picker = self.gpl_utils_source / 'rose_picker/rose_picker'
        rose_meta_conf = self.lfric_source / 'gungho/rose-meta/lfric-gungho/HEAD/rose-meta.conf'
        logger.info('rose_picker')
        run_command(
            command=[
                rose_picker, str(rose_meta_conf),
                '-directory', str(config_dir),
                '-include_dirs', self.lfric_source],
            env=env,
        )

        # "build_config_loaders"
        # builds a bunch of f90s from the json
        logger.info('GenerateNamelist')
        gen_namelist = self.lfric_source / 'infrastructure/build/tools/GenerateNamelist'
        run_command(
            command=[
                str(gen_namelist),
                '-verbose',
                str(config_dir / 'rose-meta.json'),
                '-directory', str(config_dir),
                # '--norandom_enums'
            ]
        )

        # configuration_mod.f90
        logger.info('GenerateLoader')
        gen_loader = self.lfric_source / 'infrastructure/build/tools/GenerateLoader'
        names = [name.strip() for name in open(config_dir / 'config_namelists.txt').readlines()]
        configuration_mod_fpath = working_dir / 'configuration_mod.f90'
        run_command(
            command=[
                str(gen_loader),
                configuration_mod_fpath,
                *names,
            ]
        )

        # feign_config_mod.f90
        logger.info('GenerateFeigns')
        gen_feigns = self.lfric_source / 'infrastructure/build/tools/GenerateFeigns'
        feign_config_mod_fpath = working_dir / 'feign_config_mod.f90'
        run_command(
            command=[
                str(gen_feigns),
                str(config_dir / 'rose-meta.json'),
                '-output', feign_config_mod_fpath,
            ]
        )

        # put the generated source into an artefact
        artefacts['configurator_output'] = [
            configuration_mod_fpath,
            feign_config_mod_fpath
        ]


class FparserWorkaround_StopConcatenation(Step):
    """
    fparser can't handle string concat in a stop statement. This step is a workaround.

    https://github.com/stfc/fparser/issues/330

    """
    def run(self, artefacts, config):
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
        preprocessor='fpp',
        source=FilterFpaths('psyclone_output', '.F90'),
        output_artefact='preprocessed_psyclone',
        output_suffix='.f90',
        name='preprocess psyclone output',
        common_flags=['-P'],
    )


class PsyThing(Step):

    def __init__(self, name=None, kernel_roots=None):
        super().__init__(name=name or 'psy thingy')
        self.kernel_roots = kernel_roots or []

    def run(self, artefacts: Dict, config):
        super().run(artefacts=artefacts, config=config)

        # results = self.run_mp(artefacts['preprocessed_x90'], self.do_one_file)
        x90s = FilterFpaths('all_source', '.x90')(artefacts)
        results = self.run_mp(x90s, self.do_one_file)

        errors = list(by_type(results, Exception))
        if errors:
            errs_str = '\n'.join(map(str, errors))
            logger.error(f"there were exceptions - not sure if we need to stop: {errs_str}")

        successes = list(filter(lambda r: not isinstance(r, Exception), results))
        logger.info(f"success with {len(successes)} files")
        artefacts['psyclone_output'] = []
        for files in successes:
            artefacts['psyclone_output'].extend(files)

    def do_one_file(self, x90_file):
        log_or_dot(logger=logger, msg=str(x90_file))

        generated = x90_file.parent / (str(x90_file.stem) + '_psy.f90')  # not expected to require preprocessing
        modified_alg = x90_file.with_suffix('.F90')  # may need preprocessing

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

        if self._config.debug_skip and Path(modified_alg).exists():
            logger.info(f'PsyThing skipping {x90_file}')
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
    # logging.getLogger('fab').setLevel(logging.DEBUG)

    gungho_config = gungho()
    gungho_config.run()
