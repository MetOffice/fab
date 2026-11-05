! Symbols: test_prog
! Prereqs: big_mode, cli_mod, special_mod
program test_prog
  use big_mod, only : thing_type
  use cli_mod
  type, extends(thing_type) :: whatsit_type
  end type whatsit_typetype
contains
  subroutine helper()
    use special_mod, only : stuff
  end subroutine helper
end program test_prog
