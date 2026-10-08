! (c) Crown copyright Met Office. All rights reserved.
! For further details please refer to the file COPYRIGHT
! which you should have received as part of this distribution
!
module stay_mod

    implicit none

contains

    subroutine stay(buffer)
        use constants_mod, only : str_len
        implicit none
        character(str_len), intent(out) :: buffer
        write(buffer, '(A)') 'I should stay'
    end subroutine stay

end module stay_mod
