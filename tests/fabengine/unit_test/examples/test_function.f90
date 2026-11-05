function test_func
  use big_mod, only : thing_type
  use cli_mod

contains

  subroutine helper()
    use special_mod, only : stuff
  end subroutine helper
end function test_func
