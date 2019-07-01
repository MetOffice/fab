module my_kernel_test_mod

  use pFUnit_mod
  use constants_mod, only : r_def
  use my_kernel_mod, only : my_kernel_code

  implicit none

contains

  !@test
  subroutine test_my_kernel

    implicit none

    real(r_def) :: dblock(27)
    real(r_def) :: expected(27) = (/4,5,6,7,8,9,10,11,12, &
                                    0,0,0,0,0,0,0,0,0, &
                                    0,0,0,0,0,0,0,0,0/)
    integer     :: dofs(9) = (/1,2,3,4,5,6,7,8,9/)

    call my_kernel_code( 3, dblock, 9, 27, dofs)
#line 23 "my_kernel_test_mod.pf"
  call assertEqual(expected, dblock, &
 & location=SourceLocation( &
 & 'my_kernel_test_mod.pf', &
 & 23) )
  if (anyExceptions()) return
#line 24 "my_kernel_test_mod.pf"

  end subroutine test_my_kernel

end module my_kernel_test_mod

module Wrapmy_kernel_test_mod
   use pFUnit_mod
   use my_kernel_test_mod
   implicit none
   private

contains


end module Wrapmy_kernel_test_mod

function my_kernel_test_mod_suite() result(suite)
   use pFUnit_mod
   use my_kernel_test_mod
   use Wrapmy_kernel_test_mod
   type (TestSuite) :: suite

   suite = newTestSuite('my_kernel_test_mod_suite')

   call suite%addTest(newTestMethod('test_my_kernel', test_my_kernel))


end function my_kernel_test_mod_suite

