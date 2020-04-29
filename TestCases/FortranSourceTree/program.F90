program thingumy

    use iso_fortran_env, only : output_unit
    use link_mod, only : link_choice
    use fpp_mod, only : fpp_choice

    implicit none

    write(output_unit, '("Someone made a decission")')
    write(output_unit, '("By linking choice ", I0)') link_choice()
    write(output_unit, '("By setting preprocessor variable CHOOSE to ", A)') fpp_choice()

end program thingumy
