module algorithm_mod

  use field_mod, only : field_type

  implicit none

contains

  subroutine algorithm()

    implicit none

    type(field_type) :: field

    field = field_type()
    call invoke( test_kernel( field ) )

  end subroutine algorithm

end module algorithm_mod
