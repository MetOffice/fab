##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the compiler implementation.
'''

import pytest

from fab.tools import Flags


def test_flags_constructor():
    '''Tests the constructor of Flags.'''
    f1 = Flags()
    assert isinstance(f1, list)
    assert f1 == []
    f2 = Flags(["a"])
    assert isinstance(f2, list)
    assert f2 == ["a"]


def test_remove_flags():
    '''Test remove_flags functionality.'''
    flags = Flags()
    flags.remove_flag("-c", False)
    assert flags == []

    all_flags = ['a.f90', '-c', '-o', 'a.o', '-fsyntax-only', "-J", "/tmp"]
    flags = Flags(all_flags)
    assert flags == all_flags
    with pytest.warns(UserWarning, match="Removing managed flag"):
        flags.remove_flag("-c")
    del all_flags[1]
    assert flags == all_flags
    with pytest.warns(UserWarning, match="Removing managed flag"):
        flags.remove_flag("-J", has_parameter=True)
    del all_flags[-2:]
    assert flags == all_flags

    for flags_in, expected in [(["-J", "b"], []),
                               (["-Jb"], []),
                               (["a", "-J", "c"], ["a"]),
                               (["a", "-Jc"], ["a"]),
                               (["a", "-J"], ["a"]),
                               ]:
        flags = Flags(flags_in)
        with pytest.warns(UserWarning, match="Removing managed flag"):
            flags.remove_flag("-J", has_parameter=True)
        assert flags == expected


def test_flags_checksum():
    '''Tests computation of the checksum.'''
    # I think this is a poor testing pattern.
    flags = Flags(['one', 'two', 'three', 'four'])
    assert flags.checksum() == 3011366051
