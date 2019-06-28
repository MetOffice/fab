program thing

  use iso_fortran_env, only : output_unit

  use algorithm_mod, only : algorithm
  use field_mod,     only : field_type
  use util_mod,      only : hash

  implicit none

  type(field_type) :: field

  real, target  :: something(4) = (/0.1, 1.4, 3.9, 2.7/)
  real, pointer :: some_pointer(:) => something

  write(output_unit, '("Some hash: ", I0)') hash(some_pointer)

  call algorithm(field)

end program thing
