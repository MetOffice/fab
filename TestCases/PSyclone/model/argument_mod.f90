module argument_mod

  implicit none

  private

  integer, public, parameter :: gh_field = 507
  integer, public, parameter :: gh_write = 65
  integer, public, parameter :: cells    = 396

  type, public :: arg_type
     integer :: arg_type
     integer :: arg_intent
     integer :: wspace      = -1
     integer :: from_wspace = -1
     integer :: stencil_map = -1
     integer :: mesh_arg    = -1
  end type arg_type

end module argument_mod

