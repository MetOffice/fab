#if CHOOSE == ONE
module fpp_mod

    use nosuch_mod, only : nonexistant

    implicit none

    public fpp_choice

contains

    function fpp_choice()

        implicit none

        character(3) :: fpp_choice

        fpp_choice = "ONE"

    end function fpp_choice

end module fpp_mod
#endif
