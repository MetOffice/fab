program hillfort

  use iso_fortran_env, only : input_unit, output_unit
#ifdef BEEF
  use support_mod, only : characters_in_number
#endif

  implicit none

  integer :: input = 50

  write(output_unit, '("Input is ", I0)') input

#ifdef BEEF
  write(output_unit, &
        '("Number is ", I0, " characters long")') characters_in_number(input)
#endif
  write(output_unit, '("Halving the number gives ", I0)') input / 2

end program hillfort
