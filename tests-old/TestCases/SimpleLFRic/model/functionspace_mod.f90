module functionspace_mod

  implicit none

  private

  integer, public, parameter :: W0       = 173
  integer, public, parameter :: W1       = 194
  integer, public, parameter :: W2       = 889
  integer, public, parameter :: W2V      = 857
  integer, public, parameter :: W2H      = 884
  integer, public, parameter :: W2broken = 211
  integer, public, parameter :: W2trace  = 213
  integer, public, parameter :: W3       = 424
  integer, public, parameter :: Wtheta   = 274
  integer, public, parameter :: Wchi     = 869

  type, public :: functionspace_type
    private
    integer, pointer :: dofmap(:, :)
  contains
    private
    procedure, public :: get_ncell
    procedure, public :: get_ndf
    procedure, public :: get_nlayers
    procedure, public :: get_undf
    procedure, public :: get_whole_dofmap
    ! There should be a finaliser but for testing it's too much work.
  end type functionspace_type

  interface functionspace_type
    procedure functionspace_initialise
  end interface

contains

  function functionspace_initialise() result(instance)
    implicit none
    type(functionspace_type) :: instance
    allocate( instance%dofmap(2, 1) )
  end function functionspace_initialise

  function get_ncell(this)
    implicit none
    class(functionspace_type), intent(inout) :: this
    integer :: get_ncell
    get_ncell = 1
  end function get_ncell

  function get_ndf(this)
    implicit none
    class(functionspace_type), intent(inout) :: this
    integer :: get_ndf
    get_ndf = 1
  end function get_ndf

  function get_undf(this)
    implicit none
    class(functionspace_type), intent(inout) :: this
    integer :: get_undf
    get_undf = 1
  end function get_undf

  function get_nlayers(this)
    implicit none
    class(functionspace_type), intent(inout) :: this
    integer :: get_nlayers
    get_nlayers = 1
  end function get_nlayers

  function get_whole_dofmap(this)
    implicit none
    class(functionspace_type), intent(inout) :: this
    integer, pointer :: get_whole_dofmap(:, :)
    get_whole_dofmap => this%dofmap
  end function get_whole_dofmap

end module functionspace_mod
