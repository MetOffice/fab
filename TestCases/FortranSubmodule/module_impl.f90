submodule(module_mod) module_smod

  implicit none

contains

  module function foo_initialiser( starter )
    implicit none
    integer, intent(in) :: starter
    type(foo_type) :: foo_initialiser
    foo_initialiser%stuff = starter
  end function foo_initialiser


  module subroutine mangle(this, factor)
    implicit none
    class(foo_type), intent(inout) :: this
    integer,         intent(in)    :: factor
    this%stuff = ieor(this%stuff, factor)
  end subroutine mangle


    module procedure how_much ! Alternative syntax
      how_much = this%stuff
    end procedure how_much

end submodule
