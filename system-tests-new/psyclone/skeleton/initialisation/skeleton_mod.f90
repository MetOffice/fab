!-----------------------------------------------------------------------------
! (c) Crown copyright 2017 Met Office. All rights reserved.
! The file LICENCE, distributed with this code, contains details of the terms
! under which the code may be used.
!-----------------------------------------------------------------------------

!> Skeleton miniapp program support functions.
!>
!> Originally these were "block" constructs within the program but neither
!> GNU or Intel Fortran where properly able to cope with that.
!>
module skeleton_mod

  use log_mod, only : log_event,         &
                      log_scratch_space, &
                      LOG_LEVEL_ALWAYS,  &
                      LOG_LEVEL_ERROR


  implicit none

  private
  public :: load_configuration, program_name

  character(*), parameter :: program_name = "skeleton"

contains

  !> Loads run-time configuration and ensures everything is ship-shape.
  !>
  subroutine load_configuration( filename )

    use configuration_mod, only : read_configuration, &
                                  ensure_configuration

    implicit none

    character(*), intent(in) :: filename

    character(*), parameter ::                           &
        required_configuration(5) =  [ 'base_mesh     ', &
                                       'extrusion     ', &
                                       'finite_element', &
                                       'partitioning  ', &
                                       'planet        ']

    logical              :: okay
    logical, allocatable :: success_map(:)
    integer              :: i

    allocate( success_map(size(required_configuration)) )

    call log_event( 'Loading '//program_name//' configuration ...', &
                    LOG_LEVEL_ALWAYS )

    call read_configuration( filename )

    okay = ensure_configuration( required_configuration, success_map )
    if (.not. okay) then
      write( log_scratch_space, '(A)' ) &
                             'The following required namelists were not loaded:'
      do i = 1,size(required_configuration)
        if (.not. success_map(i)) &
          log_scratch_space = trim(log_scratch_space) // ' ' &
                              // required_configuration(i)
      end do
      call log_event( log_scratch_space, LOG_LEVEL_ERROR )
    end if

    deallocate( success_map )

  end subroutine load_configuration

end module skeleton_mod
