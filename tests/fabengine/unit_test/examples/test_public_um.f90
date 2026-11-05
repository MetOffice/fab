module foo
  implicit none
  private

  public :: t_bar, abc

  type, public :: t_foo(x, y, z)
     integer :: x, y
     real :: z
  end type t_foo

  type :: t_bar(x, y, z)
     integer :: x, y
     real :: z
  end type t_bar

  integer :: abc

end module foo

program test_foo
  use foo
  implicit none

  type(t_foo(x=1, y=2, z=0.1)) :: t

  ! depends on: portio.o
  call portio()

end program test_foo
