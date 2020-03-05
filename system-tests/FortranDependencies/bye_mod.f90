! (c) Crown copyright Met Office. All rights reserved.
! For further details please refer to the file COPYRIGHT
! which you should have received as part of this distribution
!
module bye_mod

    use constants_mod, only : str_len

contains

    subroutine farewell(buffer)
        character(str_len), intent(out) :: buffer
        write(buffer, '(A)') 'Good bye'
    end subroutine

end
