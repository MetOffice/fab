module module_mod

  implicit none

  type :: foo_type
    private
    integer :: stuff
  contains
    private
    procedure, public :: mangle
    procedure, public :: how_much
  end type foo_type

  interface foo_type
    procedure foo_initialiser
  end interface foo_type

  interface
    module function foo_initialiser(starter)
      integer,intent(in) :: starter
      type(foo_type) :: foo_initialiser
    end function foo_initialiser
    module subroutine mangle(this, factor)
      class(foo_type), intent(inout) :: this
      integer,         intent(in) :: factor
    end subroutine mangle
    module function how_much(this)
      class(foo_type), intent(inout) :: this
      integer :: how_much
    end function how_much
  end interface

end module module_mod
