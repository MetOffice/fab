##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the compiler implementation.
'''

from pathlib import Path
import pytest

from fab.build_config import AddFlags
from fab.tools.flags import (AlwaysFlags, ContainFlags, FlagList, MatchFlags)
from fab.util import string_checksum


def test_always_flags(stub_configuration):
    """
    Tests the various AbstractFlags constructors.
    """

    # Constructor:
    af = AlwaysFlags()
    assert af.get_flags() == []
    af = AlwaysFlags("-g")
    assert af.get_flags() == ["-g"]
    af = AlwaysFlags(["-g", "-O2"])
    assert af.get_flags() == ["-g", "-O2"]

    # Templating
    af = AlwaysFlags(["$source", "$output"])
    assert (af.get_flags(stub_configuration) ==
            [str(stub_configuration.source_root),
            str(stub_configuration.build_output)])
    af = AlwaysFlags(["$source", "$output", "$relative"])
    file_path = Path("/my/file")
    assert (af.get_flags(stub_configuration, file_path) ==
            [str(stub_configuration.source_root),
             str(stub_configuration.build_output),
             "/my"])


def test_always_flags_remove_flags():
    '''Test remove_flags functionality.'''
    flags = AlwaysFlags()
    flags.remove_flag("-c", False)
    # pylint: disable-next=use-implicit-booleaness-not-comparison
    assert flags.get_flags() == []

    all_flags = ['a.f90', '-c', '-o', 'a.o', '-fsyntax-only', "-J", "/tmp"]
    flags = AlwaysFlags(all_flags)
    assert flags.get_flags() == all_flags
    with pytest.warns(UserWarning, match="Removing managed flag"):
        flags.remove_flag("-c")
    del all_flags[1]
    assert flags.get_flags() == all_flags
    with pytest.warns(UserWarning, match="Removing managed flag"):
        flags.remove_flag("-J", has_parameter=True)
    del all_flags[-2:]
    assert flags.get_flags() == all_flags

    for flags_in, expected in [(["-J", "b"], []),
                               (["-Jb"], []),
                               (["a", "-J", "c"], ["a"]),
                               (["a", "-Jc"], ["a"]),
                               (["a", "-J"], ["a"]),
                               ]:
        flags = AlwaysFlags(flags_in)
        with pytest.warns(UserWarning, match="Removing managed flag"):
            flags.remove_flag("-J", has_parameter=True)
        assert flags.get_flags() == expected


def test_match_flags() -> None:
    """
    Tests matching using wildcards.
    """
    mf = MatchFlags("/*", "-g")
    assert mf.get_flags(file_path=Path(".")) == []
    mf = MatchFlags("/*", ["-g", "$relative"])
    file_path = Path("/my/dir")
    assert mf.get_flags(file_path=file_path) == ["-g", "/my"]


def test_contain_flags() -> None:
    """
    Tests matching using substrings.
    """
    cf = ContainFlags(pattern="yes", flags="-g")
    assert cf.get_flags(file_path=Path(".")) == []
    cf = ContainFlags("/", ["-g", "$relative"])
    file_path = Path("/my/dir")
    assert cf.get_flags(file_path=file_path) == ["-g", "/my"]


def test_flag_list_constructor():
    '''Tests the constructor of Flags.'''
    f1 = FlagList()
    assert isinstance(f1, list)

    # pylint: disable-next=use-implicit-booleaness-not-comparison
    assert f1 == []
    f2 = FlagList(["a"])
    assert isinstance(f2, list)
    assert f2.get_flags() == ["a"]


def test_flags_adding():
    '''Tests adding flags.'''
    f1 = FlagList()
    # pylint: disable-next=use-implicit-booleaness-not-comparison
    assert f1.get_flags() == []
    f1.add_flags("-a")
    assert f1.get_flags() == ["-a"]
    f1.add_flags(["-b", "-c"])
    assert len(f1) == 2
    assert f1.get_flags() == ["-a", "-b", "-c"]
    assert len(f1) == 2
    assert f1[0].get_flags() == ["-a"]
    assert f1[1].get_flags() == ["-b", "-c"]

    # Check functionality when adding a flag object:
    af1 = AlwaysFlags("-g")
    f1 = FlagList(af1)
    assert f1 == [af1]
    assert f1.get_flags() == ["-g"]

    af2 = AlwaysFlags(["-O2", "-warn"])
    f1.add_flags(af2)
    assert f1 == [af1, af2]
    assert f1.get_flags() == ["-g", "-O2", "-warn"]


def test_remove_flags():
    '''Test remove_flags functionality. This is a subset of the remove
    tests for AlwaysFlags, just to ensure that the calls are getting
    forwarded from Flags to the AlwaysFlags implementation.
    '''
    flags = FlagList()
    flags.remove_flag("-c", False)
    # pylint: disable-next=use-implicit-booleaness-not-comparison
    assert flags == []

    all_flags = ['a.f90', '-c', '-o', 'a.o', '-fsyntax-only', "-J", "/tmp"]
    flags = FlagList(all_flags)
    assert flags.get_flags() == all_flags
    with pytest.warns(UserWarning, match="Removing managed flag"):
        flags.remove_flag("-c")
    del all_flags[1]
    assert flags.get_flags() == all_flags
    with pytest.warns(UserWarning, match="Removing managed flag"):
        flags.remove_flag("-J", has_parameter=True)
    del all_flags[-2:]
    assert flags.get_flags() == all_flags


def test_flags_checksum():
    '''Tests computation of the checksum.'''
    list_of_flags = ['one', 'two', 'three', 'four']
    flags = FlagList(list_of_flags)
    assert flags.checksum() == string_checksum(str(list_of_flags))


def test_old_addflags():
    """
    Tests that old-style AddFlags are converted to MatchFlags.
    """
    add_flags = AddFlags(match="/some/pattern", flags=["-g", "-O0"])
    flag_list = FlagList(add_flags=[add_flags])
    match_flag = flag_list[0]
    assert isinstance(match_flag, MatchFlags)
    assert match_flag._pattern == "/some/pattern"
    assert match_flag._flags == ["-g", "-O0"]

    # Provide a single AddFlags instead of a list:
    flag_list = FlagList(["-x"],
                         add_flags=AddFlags("pattern", ["-y"]))
    match_flag = flag_list[1]
    assert isinstance(match_flag, MatchFlags)
    assert match_flag._pattern == "pattern"
    assert match_flag._flags == ["-y"]
