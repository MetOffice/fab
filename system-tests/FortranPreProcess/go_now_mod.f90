! (c) Crown copyright Met Office. All rights reserved.
! For further details please refer to the file COPYRIGHT
! which you should have received as part of this distribution
!
module go_now_mod

    implicit none

contains

    subroutine go_now(buffer)
        use constants_mod, only : str_len
        implicit none
        character(str_len), intent(out) :: buffer
        write(buffer, '(A)') 'I should go now'
    end subroutine go_now

end module go_now_mod
