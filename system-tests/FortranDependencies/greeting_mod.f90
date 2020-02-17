! (c) Crown copyright Met Office. All rights reserved.
! For further details please refer to the file COPYRIGHT
! which you should have received as part of this distribution
!
module greeting_mod

    implicit none

contains

    subroutine greet(buffer)
        use constants_mod, only : str_len
        implicit none
        character(str_len), intent(out) :: buffer
        write(buffer, '(A)') 'Hello'
    end subroutine greet

end greeting_mod