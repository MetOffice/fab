! DEPENDS ON: some_file.o

SUBROUTINE external_sub
    RETURN
END SUBROUTINE external_sub

INTEGER FUNCTION external_func()
    external_func = 123
END FUNCTION external_func

MODULE foo_mod
    USE bar_mod, ONLY : foo
CONTAINS

    SUBROUTINE internal_sub
        ! DEPENDS ON: monty_func
        RETURN
    END SUBROUTINE internal_sub

    SUBROUTINE openmp_sentinel
!$ USE compute_chunk_size_mod, ONLY: compute_chunk_size  ! Note OpenMP sentinel
!$ USE test that is not a sentinel with a use statement inside
    END SUBROUTINE openmp_sentinel

    INTEGER FUNCTION internal_func()
        internal_func = 456
    END FUNCTION internal_func

END MODULE foo_mod
