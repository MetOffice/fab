!-----------------------------------------------------------------------------
! (C) Crown copyright 2017 Met Office. All rights reserved.
! The file LICENCE, distributed with this code, contains details of the terms
! under which the code may be used.
!-----------------------------------------------------------------------------
!> Drives the execution of the skeleton miniapp.
!>
!> This is a temporary solution until we have a proper driver layer.
!>
module skeleton_driver_mod

  use base_mesh_config_mod,       only : prime_mesh_name
  use checksum_alg_mod,           only : checksum_alg
  use clock_mod,                  only : clock_type
  use configuration_mod,          only : final_configuration
  use constants_mod,              only : i_def, i_native, &
                                         PRECISION_REAL, r_def
  use convert_to_upper_mod,       only : convert_to_upper
  use driver_mesh_mod,            only : init_mesh
  use driver_fem_mod,             only : init_fem
  use driver_io_mod,              only : init_io, final_io, &
                                         get_clock
  use field_mod,                  only : field_type
  use halo_comms_mod,             only : initialise_halo_comms, &
                                         finalise_halo_comms
  use init_skeleton_mod,          only : init_skeleton
  use io_config_mod,              only : write_diag
  use lfric_xios_clock_mod,       only : lfric_xios_clock_type
  use lfric_xios_context_mod,     only : lfric_xios_context_type
  use local_mesh_collection_mod,  only : local_mesh_collection, &
                                         local_mesh_collection_type
  use linked_list_mod,            only : linked_list_type
  use log_mod,                    only : log_event,          &
                                         log_set_level,      &
                                         log_scratch_space,  &
                                         initialise_logging, &
                                         finalise_logging,   &
                                         LOG_LEVEL_ALWAYS,   &
                                         LOG_LEVEL_ERROR,    &
                                         LOG_LEVEL_WARNING,  &
                                         LOG_LEVEL_INFO,     &
                                         LOG_LEVEL_DEBUG,    &
                                         LOG_LEVEL_TRACE
  use mesh_collection_mod,        only : mesh_collection, &
                                         mesh_collection_type
  use mesh_mod,                   only : mesh_type
  use mpi_mod,                    only : store_comm,    &
                                         get_comm_size, &
                                         get_comm_rank
  use planet_config_mod,          only : scaled_radius
  use skeleton_mod,               only : load_configuration, program_name
  use skeleton_alg_mod,           only : skeleton_alg
  use xios,                       only : xios_context_finalize

  implicit none

  private
  public initialise, run, finalise

  ! Prognostic fields
  type( field_type ) :: field_1

  ! Coordinate field
  type(field_type), target, dimension(3) :: chi
  type(field_type), target               :: panel_id
  type(mesh_type),  pointer              :: mesh      => null()
  type(mesh_type),  pointer              :: twod_mesh => null()

contains

  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Sets up required state in preparation for run.
  !>
  subroutine initialise( filename, model_communicator )

    use logging_config_mod, only: run_log_level,          &
                                  key_from_run_log_level, &
                                  RUN_LOG_LEVEL_ERROR,    &
                                  RUN_LOG_LEVEL_INFO,     &
                                  RUN_LOG_LEVEL_DEBUG,    &
                                  RUN_LOG_LEVEL_TRACE,    &
                                  RUN_LOG_LEVEL_WARNING

    implicit none

    character(:),      intent(in), allocatable :: filename
    integer(i_native), intent(in)              :: model_communicator

    integer(i_def)    :: total_ranks, local_rank, stencil_depth
    integer(i_native) :: log_level

    class(clock_type),      pointer :: clock => null()
    real(r_def)                     :: dt_model

    !Store the MPI communicator for later use
    call store_comm( model_communicator )

    ! Initialise halo functionality
    call initialise_halo_comms( model_communicator )

    ! and get the rank information from the virtual machine
    total_ranks = get_comm_size()
    local_rank  = get_comm_rank()

    call initialise_logging(local_rank, total_ranks, program_name)

    call load_configuration( filename )

    select case (run_log_level)
    case( RUN_LOG_LEVEL_ERROR )
      log_level = LOG_LEVEL_ERROR
    case( RUN_LOG_LEVEL_WARNING )
      log_level = LOG_LEVEL_WARNING
    case( RUN_LOG_LEVEL_INFO )
      log_level = LOG_LEVEL_INFO
    case( RUN_LOG_LEVEL_DEBUG )
      log_level = LOG_LEVEL_DEBUG
    case( RUN_LOG_LEVEL_TRACE )
      log_level = LOG_LEVEL_TRACE
    end select

    call log_set_level( log_level )

    write(log_scratch_space,'(A)')                              &
        'Runtime message logging severity set to log level: '// &
        convert_to_upper(key_from_run_log_level(run_log_level))
    call log_event( log_scratch_space, LOG_LEVEL_ALWAYS )

    write(log_scratch_space,'(A)')                        &
        'Application built with '//trim(PRECISION_REAL)// &
        '-bit real numbers'
    call log_event( log_scratch_space, LOG_LEVEL_ALWAYS )

    !-------------------------------------------------------------------------
    ! Model init
    !-------------------------------------------------------------------------
    call log_event( 'Initialising '//program_name//' ...', LOG_LEVEL_ALWAYS )

    allocate( local_mesh_collection, &
              source = local_mesh_collection_type() )

    allocate( mesh_collection, &
              source = mesh_collection_type() )

    ! Hard-code stencil depth to 1 for skeleton
    stencil_depth = 1

    ! Create the mesh
    call init_mesh( local_rank, total_ranks, stencil_depth, &
                    mesh, twod_mesh = twod_mesh )

    ! Create FEM specifics (function spaces and chi field)
    call init_fem( mesh, chi, panel_id )

    ! Initialise I/O context
    call init_io( program_name, model_communicator, chi, panel_id )

    ! Get dt from model clock
    clock => get_clock()
    dt_model = real(clock%get_seconds_per_step(), r_def)

    ! Create and initialise prognostic fields
    call init_skeleton(mesh, chi, panel_id, dt_model, field_1)

  end subroutine initialise

  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Performs time steps.
  !>
  subroutine run()

    implicit none

    class(clock_type),      pointer :: clock => null()
    logical                         :: running

    clock => get_clock()
    running = clock%tick()

    ! Call an algorithm
    call skeleton_alg(field_1)

    ! Write out output file
    call log_event(program_name//": Writing diagnostic output", LOG_LEVEL_INFO)

    if (write_diag ) then
      ! Calculation and output of diagnostics
      call field_1%write_field('skeleton_field')
    end if

  end subroutine run

  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !> Tidies up after a run.
  !>
  subroutine finalise()

    implicit none

!-----------------------------------------------------------------------------
    ! Model finalise
    !-----------------------------------------------------------------------------
    call log_event( 'Finalising '//program_name//' ...', LOG_LEVEL_ALWAYS )

    ! Write checksums to file
    call checksum_alg(program_name, field_1, 'skeleton_field_1')

    call log_event( program_name//': Miniapp completed', LOG_LEVEL_INFO )

    !-------------------------------------------------------------------------
    ! Driver layer finalise
    !-------------------------------------------------------------------------

    ! Finalise IO
    call final_io()

    ! Finalise namelist configurations
    call final_configuration()

    ! Finalise halo functionality
    call finalise_halo_comms()

    call log_event( program_name//' completed.', LOG_LEVEL_ALWAYS )

    ! Finalise the logging system
    call finalise_logging()

  end subroutine finalise

end module skeleton_driver_mod
