

module my_kernel_mod

use other_kernel_mod,              only : kernel_type

implicit none

private

!> The type declaration for the kernel. Contains the metadata needed by the Psy layer
type, public, extends(kernel_type) :: kernel_one_type
  private
  type(arg_type) :: meta_args(2) = (/                 &
       arg_type(GH_FIELD, GH_REAL, GH_WRITE, Wtheta), &
       arg_type(GH_FIELD, GH_REAL, GH_READ,  W2)      &
       /)
  integer :: operates_on = CELL_COLUMN
contains
  procedure, nopass :: kernel_one_code
end type

!> The type declaration for the kernel. Contains the metadata needed by the Psy layer
type, public, extends(kernel_type) :: kernel_two_type
  private
  type(arg_type) :: meta_args(2) = (/                 &
       arg_type(GH_FIELD, GH_REAL, GH_WRITE, Wtheta), &
       arg_type(GH_FIELD, GH_REAL, GH_READ,  W2)      &
       /)
  integer :: operates_on = CELL_COLUMN
contains
  procedure, nopass :: kernel_two_code
end type

end module my_kernel_mod
