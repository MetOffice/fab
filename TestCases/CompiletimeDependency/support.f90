module support_mod

  implicit none

  private
  public :: characters_in_number

contains

  function characters_in_number( param ) result( length )

    implicit none

    integer, intent(in) :: param
    integer :: length

    length = int(floor(log10(real(param)))) + 1

  end function characters_in_number

end module support_mod
