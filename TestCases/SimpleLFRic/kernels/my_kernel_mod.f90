module my_kernel_mod

  use argument_mod,      only : arg_type, cells, gh_field, gh_write
  use functionspace_mod, only : w3
  use kernel_mod,        only : kernel_type

  implicit none

  private

  type, public, extends(kernel_type) :: my_kernel_type
    private
    type(arg_type) :: meta_args(1) = (/ &
                                        arg_type( gh_field, gh_write, w3 ) &
                                      /)
    integer :: iterates_over = cells
  contains
    procedure, nopass :: my_kernel_code
  end type

  public :: my_kernel_code

contains

  subroutine my_kernel_code( nlayers, field_1_w3, ndf_w3, undf_w3, map_w3 )

    use constants_mod, only : r_def

    implicit none

    integer,          intent(in)  :: nlayers
    integer,          intent(in)  :: ndf_w3
    integer,          intent(in)  :: undf_w3
    real(kind=r_def), intent(out) :: field_1_w3(undf_w3)
    integer,          intent(in)  :: map_w3(ndf_w3)

    integer :: d, k

    do k=0, nlayers
      do d=0, ndf_w3
        field_1_w3(map_w3(d)) = d + k
      end do
    end do

  end subroutine my_kernel_code

end module my_kernel_mod
