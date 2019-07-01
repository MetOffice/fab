program thing

  use iso_fortran_env, only : output_unit

  use algorithm_mod, only : algorithm
  use field_mod,     only : field_type, field_proxy_type
  use util_mod,      only : hash

  implicit none

  type(field_type) :: field

  real, target  :: something(4)
  real, pointer :: some_pointer(:) => null()

  type(field_proxy_type) :: accessor

  call random_number(something)
  some_pointer => something
  write(output_unit, '("Some hash: ", I0)') hash(some_pointer)

  accessor = field%get_proxy()
  accessor%data = 1.0
  call algorithm(field)
  write(output_unit, '("Field data: ", F17.4)') accessor%data

end program thing
