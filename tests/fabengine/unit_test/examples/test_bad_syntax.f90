module bad_syntax

  invalid fortran

contains

  subroutine abc()
    write(*,*) "abc"
  end subroutine abc

end module bad_syntax
