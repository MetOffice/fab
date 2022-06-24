#!/usr/bin/env python3
import logging
import os

from fab.steps.compile_c import CompileC

from fab.build_config import BuildConfig, AddFlags
from fab.constants import BUILD_OUTPUT
from fab.steps.analyse import Analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.c_pragma_injector import CPragmaInjector
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFolder, GrabFcm
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import fortran_preprocessor, c_preprocessor
from fab.steps.root_inc_files import RootIncFiles
from fab.steps.walk_source import FindSourceFiles, Exclude, Include
from grab_lfric import lfric_source_config, gpl_utils_source_config
from lfric_common import Configurator, FparserWorkaround_StopConcatenation, psyclone_preprocessor, Psyclone

logger = logging.getLogger('fab')


# todo: optimisation path stuff


def atm_config():
    lfric_source = lfric_source_config().source_root / 'lfric'
    gpl_utils_source = gpl_utils_source_config().source_root / 'gpl_utils'

    config = BuildConfig(
        project_label='atm',
        # multiprocessing=False,
        reuse_artefacts=True,
    )

    config.steps = [

        # todo: use different dst_labels because they all go into the same folder,
        #       making it hard to see what came from where?
        # internal dependencies
        GrabFolder(src=lfric_source / 'infrastructure/source/', dst_label='lfric', name='infrastructure/source'),
        GrabFolder(src=lfric_source / 'components/driver/source/', dst_label='lfric', name='components/driver/source'),
        GrabFolder(src=lfric_source / 'components/science/source/', dst_label='lfric',
                   name='components/science/source'),
        GrabFolder(src=lfric_source / 'components/lfric-xios/source/', dst_label='lfric',
                   name='components/lfric-xios/source'),

        # coupler - oasis component
        GrabFolder(src=lfric_source / 'components/coupler-oasis/source/', dst_label='lfric',
                   name='components/coupler-oasis/source'),

        # gungho dynamical core
        GrabFolder(src=lfric_source / 'gungho/source/', dst_label='lfric', name='gungho/source'),

        # UM physics - versions as required by the LFRIC_REVISION in grab_lfric.py
        GrabFcm(src='fcm:um.xm_tr/src', dst_label='science/um', revision=110487),
        GrabFcm(src='fcm:jules.xm_tr/src', dst_label='science/jules', revision=23218),
        GrabFcm(src='fcm:socrates.xm_tr/src', dst_label='science/socrates', revision='um12.2'),
        GrabFcm(src='fcm:shumlib.xm_tr/', dst_label='science/shumlib', revision='um12.2'),
        GrabFcm(src='fcm:casim.xm_tr/src', dst_label='science/casim', revision='um12.2'),

        GrabFolder(src=lfric_source / 'um_physics/source/', dst_label='lfric', name='um_physics/source'),
        GrabFolder(src=lfric_source / 'socrates/source/', dst_label='lfric', name='socrates/source'),
        GrabFolder(src=lfric_source / 'jules/source/', dst_label='lfric', name='jules/source'),

        # lfric_atm
        GrabFolder(src=lfric_source / 'lfric_atm/source/', dst_label='lfric', name='lfric_atm/source'),

        # generate more source files in source and source/configuration
        Configurator(lfric_source=lfric_source,
                     gpl_utils_source=gpl_utils_source,
                     rose_meta_conf=lfric_source / 'lfric_atm/rose-meta/lfric-lfric_atm/HEAD/rose-meta.conf',
                     config_dir=config.source_root / 'lfric/configuration'),

        FindSourceFiles(path_filters=file_filtering(config)),

        RootIncFiles(),

        # todo: bundle this in with the preprocessor, for a better ux?
        CPragmaInjector(),

        c_preprocessor(
            path_flags=[
                AddFlags(match="$source/science/um/*", flags=['-I$relative/include']),
                AddFlags(match="$source/science/shumlib/*", flags=['-I$source/science/shumlib/common/src']),
                AddFlags(match='$source/science/um/controls/c_code/*', flags=[
                    '-I$source/science/um/include/other',
                    '-I$source/science/shumlib/shum_thread_utils/src']),
            ],
        ),

        fortran_preprocessor(
            preprocessor='cpp -traditional-cpp -P',
            common_flags=['-DRDEF_PRECISION=64', '-DUSE_XIOS', '-DUM_PHYSICS', '-DCOUPLED', '-DUSE_MPI=YES'],
            path_flags=[
                AddFlags(match="$source/science/um/*", flags=['-I$relative/include']),
                AddFlags(match="$source/science/jules/*", flags=['-DUM_JULES', '-I$output']),
                AddFlags(match="$source/science/*", flags=['-DLFRIC']),
            ],
        ),

        psyclone_preprocessor(set_um_physics=True),

        Psyclone(kernel_roots=[config.project_workspace / BUILD_OUTPUT]),

        # todo: do we need this one in here?
        FparserWorkaround_StopConcatenation(name='fparser stop bug workaround'),

        Analyse(
            root_symbol='lfric_atm',
            ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        ),

        CompileC(compiler='gcc', common_flags=['-c', '-std=c99']),

        CompileFortran(
            compiler=os.getenv('FC', 'gfortran'),
            common_flags=[
                '-c', '-J', '$output',

                '-ffree-line-length-none', '-fopenmp',
                '-g',
                '-finit-integer=31173', '-finit-real=snan', '-finit-logical=true', '-finit-character=85',
                '-fcheck=all,no-bounds', '-ffpe-trap=invalid,zero,overflow',

                '-Og',

                '-Wall', '-Werror=character-truncation', '-Werror=unused-value', '-Werror=tabs',

            ],
            path_flags=[
                AddFlags('$output/science/*', ['-fdefault-real-8', '-fdefault-double-8']),
            ]
        ),

        ArchiveObjects(output_fpath='$output/objects.a'),

        LinkExe(
            linker='mpifort',
            flags=[
                '-lyaxt', '-lyaxt_c', '-lnetcdff', '-lnetcdf', '-lhdf5',  # EXTERNAL_DYNAMIC_LIBRARIES
                '-lxios',  # EXTERNAL_STATIC_LIBRARIES
                '-lstdc++',

                '-fopenmp',
            ],
        ),

    ]
    return config


def file_filtering(config):
    """Based on lfric_atm/fcm-make/extract.cfg"""

    science_root = config.source_root / 'science'

    return [
        Exclude('unit-test', '/test/'),

        # um
        Exclude(science_root / 'um'),

        Include(science_root / 'um/atmosphere/AC_assimilation/iau_mod.F90'),
        Include(science_root / 'um/atmosphere/aerosols'),
        Include(science_root / 'um/atmosphere/atmosphere_service'),
        Include(science_root / 'um/atmosphere/boundary_layer'),
        Include(science_root / 'um/atmosphere/carbon/carbon_options_mod.F90'),

        Include(science_root / 'um/atmosphere/convection'),
        Exclude(science_root / 'um/atmosphere/convection/comorph'),
        Include(science_root / 'um/atmosphere/convection/comorph/control/comorph_constants_mod.F90'),

        Include(science_root / 'um/atmosphere/diffusion_and_filtering/leonard_incs_mod.F90'),
        Include(science_root / 'um/atmosphere/diffusion_and_filtering/turb_diff_ctl_mod.F90'),
        Include(science_root / 'um/atmosphere/diffusion_and_filtering/turb_diff_mod.F90'),
        Include(science_root / 'um/atmosphere/dynamics'),
        Include(science_root / 'um/atmosphere/dynamics_advection'),
        Include(science_root / 'um/atmosphere/electric'),
        Include(science_root / 'um/atmosphere/energy_correction/eng_corr_inputs_mod.F90'),
        Include(science_root / 'um/atmosphere/energy_correction/flux_diag-fldiag1a.F90'),
        Include(science_root / 'um/atmosphere/free_tracers/free_tracers_inputs_mod.F90'),
        Include(science_root / 'um/atmosphere/idealised'),
        Include(science_root / 'um/atmosphere/large_scale_cloud'),
        Include(science_root / 'um/atmosphere/large_scale_precipitation'),
        Include(science_root / 'um/atmosphere/PWS_diagnostics/pws_diags_mod.F90'),
        Include(science_root / 'um/atmosphere/radiation_control/def_easyaerosol.F90'),
        Include(science_root / 'um/atmosphere/radiation_control/easyaerosol_mod.F90'),
        Include(science_root / 'um/atmosphere/radiation_control/easyaerosol_option_mod.F90'),
        Include(science_root / 'um/atmosphere/radiation_control/easyaerosol_read_input_mod.F90'),
        Include(science_root / 'um/atmosphere/radiation_control/fsd_parameters_mod.F90'),
        Include(science_root / 'um/atmosphere/radiation_control/max_calls.F90'),
        Include(science_root / 'um/atmosphere/radiation_control/r2_calc_total_cloud_cover.F90'),
        Include(science_root / 'um/atmosphere/radiation_control/rad_input_mod.F90'),
        Include(science_root / 'um/atmosphere/radiation_control/solinc_data.F90'),
        Include(science_root / 'um/atmosphere/radiation_control/spec_sw_lw.F90'),
        Include(science_root / 'um/atmosphere/stochastic_physics/stochastic_physics_run_mod.F90'),
        Include(science_root / 'um/atmosphere/tracer_advection/trsrce-trsrce2a.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_bedriv.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_bimol.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_cdrive.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_chem_flux_diags.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_cinit.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_diffun.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_findreaction.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_flux_dat.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_ftoy.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_fuljac.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_fyfixr.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_fyinit.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_fyself.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_hetero.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_impact.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_inicnt.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_inicnt_col_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_inijac.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_inimpct.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_inix.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_inrats.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_jac.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_posthet.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_prls.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_setsteady.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_sparse_vars.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_spimpmjp.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_spmjpdriv.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_steady.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_totnud.F90'),
        Include(science_root / 'um/atmosphere/UKCA/asad_trimol.F90'),
        Include(science_root / 'um/atmosphere/UKCA/fastjx_data.F90'),
        Include(science_root / 'um/atmosphere/UKCA/get_emdiag_stash_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/get_molmass_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/get_nmvoc_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/get_noy_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/param2d_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsbrcl_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsccl4_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acscnit_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acscos_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acscs2_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsdbrm_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsf11_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsf12_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsf22_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsh2o2_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsh2so4_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acshno3_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsmc_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsmena_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsn2o5_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsn2o_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsno2_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsno_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acso3_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acso3w_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acsso3_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acssr_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/acssrw_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/calcjs_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/cso2o3_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/ei1_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/ei2_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/ei3_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/fill_spectra_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/inijtab_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/invert_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/isrchfgt_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/lubksb_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/ludcmp_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/lymana_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/quanto12_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/quanto1d_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/scatcs_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/settab_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/setzen_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/ukca_crossec_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/ukca_parpho_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/ukca_stdto3_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/photolib/ukca_tbjs_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/spcrg3a_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_abdulrazzak_ghan.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_activ_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_activate.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_add_emiss_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_aer_no3_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_aero_ctl.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_aero_step.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_aerod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_age_air_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_ageing.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_api_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_be_drydep.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_be_wetdep.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_binapara_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_calc_coag_kernel.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_calc_drydiam.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_calc_rho_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_calc_ozonecol_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_calcminmaxgc.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_calcminmaxndmdt.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_calcnucrate.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_cdnc_jones_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_ch4_stratloss.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_check_md_nd.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_check_radaer_coupling_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chem1_dat.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chem_aer.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chem_defs_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chem_diags_allts_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chem_diags_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chem_master.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chem_offline.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chem_raq.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chem_raqaero_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chemco.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chemco_raq.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chemco_raq_init_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chemistry_ctl.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chemistry_ctl_BE_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_chemistry_ctl_col_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_cloudproc.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_coag_coff_v.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_coagwithnucl.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_cond_coff_v.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_conden.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_config_defs_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_config_specification_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_conserve_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_constants.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_cspecies.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_curve_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_d1_defs.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_day_of_week_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_dcoff_par_av_k.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_ddcalc.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_ddepaer_coeff_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_ddepaer_incl_sedi_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_ddepaer_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_ddepctl.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_ddepo3_ocean_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_ddeprt.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_deriv.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_deriv_aero.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_deriv_raq.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_deriv_raqaero_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_dissoc.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_diurnal_isop_ems.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_diurnal_oxidant.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_drydep.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_drydiam_field_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_eg_tracers_total_mass_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_emdiags_struct_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_emiss_api_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_emiss_ctl_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_emiss_diags_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_emiss_diags_mode_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_emiss_factors.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_emiss_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_emiss_mode_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_emiss_struct_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_environment_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_environment_rdim_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_environment_req_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_environment_check_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_environment_fields_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_error_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_fdiss.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_fdiss_constant_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_fieldname_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_fixeds.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_fracdiss.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_hetero_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_impc_scav.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_impc_scav_dust_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_inddep.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_ingridg.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_iniasad.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_init.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_inwdep.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_light.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_light_ctl.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_main1-ukca_main1.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_mode_check_artefacts_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_mode_diags_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_mode_setup.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_mode_tracer_maps_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_mode_verbose_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_nmspec_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_ntp_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_offline_oxidants_diags_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_option_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_photo_scheme_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_photol.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_pm_diags_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_pr_inputs_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_prim_du_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_prim_moc.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_prim_ss.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_prod_no3_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_radaer_band_average.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_radaer_lut_in.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_radaer_lut_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_radaer_populate_lut_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_radaer_precalc_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_radaer_prepare.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_radaer_read_precalc.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_radaer_ri_calc_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_radaer_struct_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_radaer_tlut_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_rainout.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_raq_diags_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_remode.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_scavenging_diags_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_scavenging_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_scenario_common.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_scenario_ctl_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_scenario_prescribed.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_scenario_wmoa1.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_sediment.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_setup_chem_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_setup_indices.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_setup_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_step_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_step_control_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_solang.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_solflux.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_solvecoagnucl_v.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_stratf.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_surfddr.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_top_boundary.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_time_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_tracer_stash.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_tracer_vars.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_tracers_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_transform_halogen.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_trop_hetchem.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_tropopause.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_um_strat_photol_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_update_emdiagstruct_mod.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_vapour.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_vgrav_av_k.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_volcanic_so2.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_volume_mode.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_water_content_v.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_wdeprt.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_wetdep.F90'),
        Include(science_root / 'um/atmosphere/UKCA/ukca_wetox.F90'),
        Include(science_root / 'um/atmosphere/GLOMAP_CLIM/get_gc_aerosol_fields_1d_mod.F90'),
        Include(science_root / 'um/atmosphere/GLOMAP_CLIM/glomap_clim_calc_aird_mod.F90'),
        Include(science_root / 'um/atmosphere/GLOMAP_CLIM/glomap_clim_calc_rh_frac_clear_mod.F90'),
        Include(science_root / 'um/atmosphere/GLOMAP_CLIM/glomap_clim_calc_md_mdt_nd_mod.F90'),
        Include(science_root / 'um/atmosphere/GLOMAP_CLIM/glomap_clim_option_mod.F90'),
        Include(science_root / 'um/atmosphere/GLOMAP_CLIM/glomap_clim_calc_aird_mod.F90'),
        Include(science_root / 'um/atmosphere/GLOMAP_CLIM/glomap_clim_pop_md_mdt_nd_mod.F90'),
        Include(science_root / 'um/control/dummy_libs/drhook/parkind1.F90'),
        Include(science_root / 'um/control/dummy_libs/drhook/yomhook.F90'),
        Include(science_root / 'um/control/grids'),
        Include(science_root / 'um/control/misc'),
        Include(science_root / 'um/control/mpp/decomp_params.F90'),
        Include(science_root / 'um/control/mpp/um_parcore.F90'),
        Include(science_root / 'um/control/mpp/um_parparams.F90'),
        Include(science_root / 'um/control/mpp/um_parvars.F90'),
        Include(science_root / 'um/control/stash/copydiag_3d_mod.F90'),
        Include(science_root / 'um/control/stash/copydiag_mod.F90'),
        Include(science_root / 'um/control/stash/cstash_mod.F90'),
        Include(science_root / 'um/control/stash/profilename_length_mod.F90'),
        Include(science_root / 'um/control/stash/set_levels_list.F90'),
        Include(science_root / 'um/control/stash/set_pseudo_list.F90'),
        Include(science_root / 'um/control/stash/stash_array_mod.F90'),
        Include(science_root / 'um/control/stash/stparam_mod.F90'),
        Include(science_root / 'um/control/stash/um_stashcode_mod.F90'),
        Include(science_root / 'um/control/top_level'),
        Include(science_root / 'um/scm/modules/scmoptype_defn.F90'),
        Include(science_root / 'um/scm/modules/s_scmop_mod.F90'),
        Include(science_root / 'um/scm/modules/scm_convss_dg_mod.F90'),
        Include(science_root / 'um/scm/stub/dgnstcs_glue_conv.F90'),
        Include(science_root / 'um/scm/stub/scmoutput_stub.F90'),
        Include(science_root / 'um/atmosphere/COSP/cosp_input_mod.F90'),
        Include(science_root / 'um/control/coupling'),
        Include(science_root / 'um/atmosphere/gravity_wave_drag/g_wave_input_mod.F90'),
        Include(science_root / 'um/atmosphere/gravity_wave_drag/gw_ussp_prec_mod.F90'),
        Include(science_root / 'um/atmosphere/gravity_wave_drag/gw_ussp_params_mod.F90'),
        Include(science_root / 'um/atmosphere/gravity_wave_drag/gw_ussp_core_mod.F90'),
        Include(science_root / 'um/atmosphere/gravity_wave_drag/gw_ussp_mod.F90'),
        Include(science_root / 'um/atmosphere/gravity_wave_drag/gw_block.F90'),
        Include(science_root / 'um/atmosphere/gravity_wave_drag/gw_wave.F90'),
        Include(science_root / 'um/atmosphere/gravity_wave_drag/gw_setup.F90'),
        Include(science_root / 'um/atmosphere/gravity_wave_drag/c_gwave_mod.F90'),
        Include(science_root / 'um/utility/qxreconf/calc_fit_fsat.F90'),


        Exclude(science_root / 'jules'),

        Include(science_root / 'jules/control/shared'),
        Include(science_root / 'jules/control/cable/shared'),
        Include(science_root / 'jules/control/cable/standalone/cable_fields_mod.F90'),
        Include(science_root / 'jules/initialisation/cable/grid_constants_cbl.F90'),
        Include(science_root / 'jules/control/standalone/jules_fields_mod.F90'),
        Include(science_root / 'jules/util/shared/gridbox_mean_mod.F90'),
        Include(science_root / 'jules/util/shared/metstats/metstats_mod.F90'),
        Include(science_root / 'jules/initialisation/shared/allocate_jules_arrays.F90'),
        Include(science_root / 'jules/initialisation/shared/freeze_soil.F90'),
        Include(science_root / 'jules/science/params'),
        Include(science_root / 'jules/science/radiation'),
        Include(science_root / 'jules/science/snow'),
        Include(science_root / 'jules/science/soil'),
        Include(science_root / 'jules/science/surface'),
        Include(science_root / 'jules/science/vegetation'),


        Exclude(science_root / 'socrates'),

        Include(science_root / 'socrates/radiance_core'),
        Include(science_root / 'socrates/interface_core'),
        Include(science_root / 'socrates/illumination/astro_constants_mod.F90'),
        Include(science_root / 'socrates/illumination/def_orbit.F90'),
        Include(science_root / 'socrates/illumination/orbprm_mod.F90'),
        Include(science_root / 'socrates/illumination/socrates_illuminate.F90'),
        Include(science_root / 'socrates/illumination/solang_mod.F90'),
        Include(science_root / 'socrates/illumination/solpos_mod.F90'),


        Exclude(science_root / 'casim'),

        Include(science_root / 'casim/mphys_parameters.F90'),
        Include(science_root / 'casim/variable_precision.F90'),
        Include(science_root / 'casim/special.F90'),
        Include(science_root / 'casim/thresholds.F90'),


        Exclude(science_root / 'shumlib'),

        Include(science_root / 'shumlib/shum_wgdos_packing/src'),
        Include(science_root / 'shumlib/shum_string_conv/src'),
        Include(science_root / 'shumlib/shum_latlon_eq_grids/src'),
        Include(science_root / 'shumlib/shum_horizontal_field_interp/src'),
        Include(science_root / 'shumlib/shum_spiral_search/src'),
        Include(science_root / 'shumlib/shum_constants/src'),
        Include(science_root / 'shumlib/shum_thread_utils/src'),
        Include(science_root / 'shumlib/shum_data_conv/src'),
        Include(science_root / 'shumlib/shum_number_tools/src'),
        Include(science_root / 'shumlib/shum_byteswap/src'),

        Include(science_root / 'shumlib/common/src'),
        Exclude(science_root / 'shumlib/common/src/shumlib_version.c'),

    ]


if __name__ == '__main__':
    # logger.setLevel(logging.DEBUG)
    atm_config().run()
