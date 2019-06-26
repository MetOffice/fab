program test

  use iso_fortran_env, only : output_unit
  use module_mod,      only : foo_type

  implicit none

  type(foo_type) :: instance

  instance = foo_type(12)

  write(output_unit, '("Start with ", I0)') instance%how_much()
  call instance%mangle(17)
  write(output_unit, '("After mangle ", I0)') instance%how_much()

end program test
