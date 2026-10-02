module mod_with_contain

contains
    subroutine my_sub()
        call contained()
    contains
        subroutine contained()
        end subroutine contained
    end subroutine my_sub

end module mod_with_contain
