!-----------------------------------------------------------------------------
! (C) Crown copyright 2021 Met Office. All rights reserved.
! The file LICENCE, distributed with this code, contains details of the terms
! under which the code may be used.
!-----------------------------------------------------------------------------

!> @brief Utility for aborting LFRic models

module lfric_abort_mod

  implicit none

contains

  !> @brief     Call abort on the global MPI communicator
  !> If the code is being run with MPI, then mpi_abort should be called.
  !> Currently, the global communicator is used. This would require updating
  !> if support for applications coupled with other MPI applications is required
  !> @param[in] ierr  Error code
  subroutine parallel_abort(ierr)

    use mpi, only : mpi_abort, MPI_COMM_WORLD

    implicit none

    integer, intent(in) :: ierr

    integer :: ierror

    call mpi_abort(MPI_COMM_WORLD, ierr, ierror)

  end subroutine parallel_abort

end module lfric_abort_mod
