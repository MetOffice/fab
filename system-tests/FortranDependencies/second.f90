! (c) Crown copyright Met Office. All rights reserved.
! For further details please refer to the file COPYRIGHT
! which you should have received as part of this distribution
!
program second

    use, intrinsic :: iso_fortran_env, only : output_unit
    use constants_mod, only : str_len
    use :: bye_mod,    only : farewell

    character(str_len) :: message

    call farewell(message)

    write(output_unit, '(A)') message

end program second
