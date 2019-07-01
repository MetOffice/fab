module stuff_test_mod

  use pFUnit_mod
  use stuff_mod, only : number

  implicit none

contains

  !@test
  subroutine test_number_okay()

    implicit none

    integer :: result

    result = number()
#line 18 "stuff_test.pf"
  call assertEqual( 42, result , &
 & location=SourceLocation( &
 & 'stuff_test.pf', &
 & 18) )
  if (anyExceptions()) return
#line 19 "stuff_test.pf"

  end subroutine test_number_okay

end module stuff_test_mod

module Wrapstuff_test_mod
   use pFUnit_mod
   use stuff_test_mod
   implicit none
   private

contains


end module Wrapstuff_test_mod

function stuff_test_mod_suite() result(suite)
   use pFUnit_mod
   use stuff_test_mod
   use Wrapstuff_test_mod
   type (TestSuite) :: suite

   suite = newTestSuite('stuff_test_mod_suite')

   call suite%addTest(newTestMethod('test_number_okay', test_number_okay))


end function stuff_test_mod_suite

