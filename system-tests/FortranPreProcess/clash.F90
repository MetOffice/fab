! (c) Crown copyright Met Office. All rights reserved.
! For further details please refer to the file COPYRIGHT
! which you should have received as part of this distribution
!
program stay_or_go_now

    use constants_mod, only : str_len
#if defined(SHOULD_I_STAY)
    use stay_mod,     only  : stay
#else
    use go_now_mod, only: go_now
#endif

    character(str_len) :: message

#if defined(SHOULD_I_STAY)
    call stay(message)
#else
    call go_now(message)
#endif

    write(output_unit, '(A)') message

end program stay_or_go_now
