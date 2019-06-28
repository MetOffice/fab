module field_mod

  use constants_mod,     only : r_def
  use functionspace_mod, only : functionspace_type
  use mesh_mod,          only : mesh_type

  implicit none

  private

  type, public :: field_type
    private
    type(mesh_type), pointer :: mesh
  contains
    private
    procedure, public :: get_mesh
    procedure, public :: get_proxy
    ! There should be a finalising but I can't be bothered
  end type field_type

  interface field_type
    procedure :: field_initialiser
  end interface field_type

  type, public :: field_proxy_type
    private
    real(r_def), public :: data(10)
    type(functionspace_type), public :: vspace
  contains
    procedure set_dirty
  end type field_proxy_type

contains

  function field_initialiser() result(instance)
    implicit none
    type(field_type) :: instance
    allocate( instance%mesh )
  end function field_initialiser

  function get_mesh(this)
    implicit none
    class(field_type), intent(inout) :: this
    type(mesh_type), pointer :: get_mesh
    get_mesh => this%mesh
  end function get_mesh

  function get_proxy(this)
    implicit none
    class(field_type), intent(inout) :: this
    type(field_proxy_type) :: get_proxy
    get_proxy%vspace = functionspace_type()
  end function get_proxy

  subroutine set_dirty(this)
    implicit none
    class(field_Proxy_type), intent(inout) :: this
  end subroutine set_dirty
end module field_mod
