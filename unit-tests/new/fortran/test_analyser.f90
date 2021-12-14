! DEPENDS ON: some_file.o

SUBROUTINE external_sub
    RETURN
END SUBROUTINE external_sub

INTEGER FUNCTION external_func()
    external_func = 123
END FUNCTION external_func

MODULE foo_mod
    USE bar_mod, ONLY: foo
    CONTAINS

    SUBROUTINE interrnal_sub
        ! DEPENDS ON: monty_func
        RETURN
    END SUBROUTINE interrnal_sub

    INTEGER FUNCTION internal_func()
        internal_func = 456
    END FUNCTION internal_func

END MODULE foo_mod
