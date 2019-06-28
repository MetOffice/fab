module field_mod

  use constants_mod,     only : r_def
  use functionspace_mod, only : functionspace_type

  implicit none

  private

  type, public :: field_type
    private
  contains
    private
    procedure, public :: get_proxy
  end type field_type

  type, public :: field_proxy_type
    private
    real(r_def), public :: data(10)
    type(functionspace_type), public :: vspace
  end type field_proxy_type

contains

  function get_proxy(this)
    implicit none
    class(field_type), intent(inout) :: this
    type(field_proxy_type) :: get_proxy
    get_proxy%vspace = functionspace_type()
  end function get_proxy

end module field_mod
