! Symbols: test_mod
! Prereqs: big_mod, cli_mod
module test_mod
  use big_mod, only : thing_type
  use cli_mod
contains
  subroutine helper()
    use special_mod, only : stuff
  end subroutine helper
end module test_mod
