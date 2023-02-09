
module matrix_vector_kernel_mod
  use argument_mod,            only : arg_type,                 &
                                      GH_FIELD, GH_OPERATOR,    &
                                      GH_REAL, GH_READ, GH_INC, &
                                      ANY_SPACE_1, ANY_SPACE_2, &
                                      CELL_COLUMN
  use constants_mod,           only : i_def, r_single, r_double
  use kernel_mod,              only : kernel_type

  implicit none

  private

  type, public, extends(kernel_type) :: matrix_vector_kernel_type
    private
    type(arg_type) :: meta_args(3) = (/                                    &
         arg_type(GH_FIELD,    GH_REAL, GH_INC,  ANY_SPACE_1),             &
         arg_type(GH_FIELD,    GH_REAL, GH_READ, ANY_SPACE_2),             &
         arg_type(GH_OPERATOR, GH_REAL, GH_READ, ANY_SPACE_1, ANY_SPACE_2) &
         /)
    integer :: operates_on = CELL_COLUMN
  end type

  public :: matrix_vector_code

  interface matrix_vector_code
    module procedure  &
      matrix_vector_code_r_single, &
      matrix_vector_code_r_double
  end interface

contains

  subroutine matrix_vector_code_r_single(cell,              &
                                         nlayers,           &
                                         lhs, x,            &
                                         ncell_3d,          &
                                         matrix,            &
                                         ndf1, undf1, map1, &
                                         ndf2, undf2, map2)

    implicit none

    ! Arguments
    integer(kind=i_def),                  intent(in) :: cell, nlayers, ncell_3d
    integer(kind=i_def),                  intent(in) :: undf1, ndf1
    integer(kind=i_def),                  intent(in) :: undf2, ndf2
    integer(kind=i_def), dimension(ndf1), intent(in) :: map1
    integer(kind=i_def), dimension(ndf2), intent(in) :: map2
    real(kind=r_single), dimension(undf2),              intent(in)    :: x
    real(kind=r_single), dimension(undf1),              intent(inout) :: lhs
    real(kind=r_single), dimension(ndf1,ndf2,ncell_3d), intent(in)    :: matrix

    ! Internal variables
    integer(kind=i_def)                  :: df, k, ik
    real(kind=r_single), dimension(ndf2) :: x_e
    real(kind=r_single), dimension(ndf1) :: lhs_e

  end subroutine matrix_vector_code_r_single

  subroutine matrix_vector_code_r_double(cell,              &
                                         nlayers,           &
                                         lhs, x,            &
                                         ncell_3d,          &
                                         matrix,            &
                                         ndf1, undf1, map1, &
                                         ndf2, undf2, map2)

    implicit none

    ! Arguments
    integer(kind=i_def),                  intent(in) :: cell, nlayers, ncell_3d
    integer(kind=i_def),                  intent(in) :: undf1, ndf1
    integer(kind=i_def),                  intent(in) :: undf2, ndf2
    integer(kind=i_def), dimension(ndf1), intent(in) :: map1
    integer(kind=i_def), dimension(ndf2), intent(in) :: map2
    real(kind=r_double), dimension(undf2),              intent(in)    :: x
    real(kind=r_double), dimension(undf1),              intent(inout) :: lhs
    real(kind=r_double), dimension(ndf1,ndf2,ncell_3d), intent(in)    :: matrix

    ! Internal variables
    integer(kind=i_def)                  :: df, k, ik
    real(kind=r_double), dimension(ndf2) :: x_e
    real(kind=r_double), dimension(ndf1) :: lhs_e

  end subroutine matrix_vector_code_r_double

end module matrix_vector_kernel_mod
