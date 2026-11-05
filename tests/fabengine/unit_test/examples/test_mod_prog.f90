!
! Valid Fortran program which combines internal and external
! dependencies, as well as a UM-style dependency comment.
!
module edam
contains
  subroutine wax_cover
    write (*,*) "Edam is as waxy as the moon"
  end subroutine wax_cover
end module edam

program example1
  use stilton
  use edam
  ! depends on: gruyere
  call yoghurt
contains
  subroutine yoghurt
    write (*,*) "Very tasty yoghurt"
  end subroutine yoghurt
end program example1
