subroutine test_sub
  use big_mod, only : thing_type
  use cli_mod

contains

  subroutine helper()
    use special_mod, only : stuff
  end subroutine helper
end subroutine test_sub
