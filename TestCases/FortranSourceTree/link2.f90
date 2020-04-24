module link_mod

    implicit none

    public link_choice

contains

    function link_choice()

        implicit none

        integer :: link_choice

        link_choice = 2

    end function link_choice

end module link_mod