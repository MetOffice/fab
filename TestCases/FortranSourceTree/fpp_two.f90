#if CHOOSE == TWO
module fpp_mod

    implicit none

    public fpp_choice

contains

    function fpp_choice()

        implicit none

        character(3) :: fpp_choice

        fpp_choice = "TWO"

    end function fpp_choice

end module fpp_mod
#endif
