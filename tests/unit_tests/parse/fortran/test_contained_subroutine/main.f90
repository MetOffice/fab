program main
    use mod_with_contain, only: my_sub

contains
    subroutine should_not_be_exported
    end subroutine should_not_be_exported
end program main
