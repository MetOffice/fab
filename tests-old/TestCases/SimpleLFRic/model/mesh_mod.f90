module mesh_mod

  implicit none

  private

  type, public :: mesh_type
    private
  contains
    procedure get_last_edge_cell
  end type mesh_type

contains

  function get_last_edge_cell(this)
    implicit none
    class(mesh_type), intent(inout) :: this
    integer :: get_last_edge_cell
    get_last_edge_cell = 1
  end function get_last_edge_cell

end module mesh_mod
