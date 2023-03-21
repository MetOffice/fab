#if CHOOSE == TWO
module fpp_mod

    implicit none

    public fpp_choice

contains

    function fpp_choice()

        use unfound_mod, only : not_there

        implicit none

        character(3) :: fpp_choice

        fpp_choice = "TWO"

    end function fpp_choice

end module fpp_mod
#endif
