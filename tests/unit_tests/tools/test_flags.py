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
from fab.tools.flags import (AlwaysFlags, ContainFlags, FlagList, MatchFlags,
                             ProfileFlags)
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


def test_profile_flags_with_profile():
    '''Tests adding flags.'''
    pf = ProfileFlags()
    pf.define_profile("base")
    assert pf["base"] == []
    pf.add_flags("-base", "base")

    assert len(pf["base"]) == 1
    assert isinstance(pf["base"][0], AlwaysFlags)
    assert pf["base"][0].get_flags() == ["-base"]

    pf.add_flags(["-base2", "-base3"], "base")
    assert len(pf["base"]) == 2
    assert isinstance(pf["base"][0], AlwaysFlags)
    assert isinstance(pf["base"][1], AlwaysFlags)
    assert pf["base"][0].get_flags() == ["-base"]
    assert pf["base"][1].get_flags() == ["-base2", "-base3"]

    # Check that we get an exception if we specify a profile
    # that does not exist
    with pytest.raises(KeyError) as err:
        _ = pf["does_not_exist"]
    assert "Profile 'does_not_exist' is not defined" in str(err.value)


def test_profile_flags_constructor_args():
    '''Tests various constructor argument combinations.'''
    pf = ProfileFlags("-g")
    assert len(pf[""]) == 1
    assert isinstance(pf[""][0], AlwaysFlags)
    assert pf[""][0].get_flags() == ["-g"]

    pf = ProfileFlags("-g", profile="prof")
    assert pf[""] == []
    assert len(pf["prof"]) == 1
    assert isinstance(pf["prof"][0], AlwaysFlags)
    assert pf["prof"][0].get_flags() == ["-g"]


def test_profile_flags_without_profile():
    '''Tests adding flags.'''
    pf = ProfileFlags()
    assert pf[""] == []
    assert pf[None] == []
    pf.add_flags("-base")
    assert len(pf[""]) == 1
    assert isinstance(pf[""][0], AlwaysFlags)
    assert pf[""][0].get_flags() == ["-base"]
    pf.add_flags(["-base2", "-base3"])
    assert len(pf[""]) == 2
    assert pf[""][0].get_flags() == ["-base"]
    assert pf[""][1].get_flags() == ["-base2", "-base3"]

    # Check that we get an exception if we specify a profile
    with pytest.raises(KeyError) as err:
        _ = pf["does_not_exist"]
    assert "Profile 'does_not_exist' is not defined" in str(err.value)

    # Check that we get an exception if we try to inherit from a profile
    # that does not exist
    with pytest.raises(KeyError) as err:
        pf.define_profile("new_profile", "does_not_exist")
    assert ("Inherited profile 'does_not_exist' is not defined."
            in str(err.value))

    # Test that inheriting from the default profile "" works
    pf.define_profile("from_default", "")
    assert pf._inherit_from["from_default"] == ""


def test_profile_flags_inheriting(stub_configuration):
    '''Tests adding flags.'''
    pf = ProfileFlags()
    pf.define_profile("base")
    assert pf["base"] == []
    # And there should not be any inherited profile defined:
    assert "base" not in pf._inherit_from

    pf.add_flags("-base", "base")
    stub_configuration.set_profile("base")
    assert pf.get_flags(stub_configuration) == ["-base"]

    pf.define_profile("derived", "base")
    stub_configuration.set_profile("derived")
    assert pf.get_flags(stub_configuration) == ["-base"]
    assert pf._inherit_from["derived"] == "base"
    pf.add_flags("-derived", "derived")
    assert pf.get_flags(stub_configuration) == ["-base", "-derived"]

    pf.define_profile("derived2", "derived")
    stub_configuration.set_profile("derived2")
    assert pf.get_flags(stub_configuration) == ["-base", "-derived"]
    pf.add_flags("-derived2", "derived2")
    assert pf.get_flags(stub_configuration) == ["-base", "-derived",
                                                "-derived2"]


def test_profile_flags_removing(stub_configuration):
    '''Tests adding flags.'''
    pf = ProfileFlags()
    pf.define_profile("base")
    assert pf["base"] == []
    pf.add_flags(["-base1", "-base2"], "base")
    warn_message = "Removing managed flag '-base1'."
    with pytest.warns(UserWarning, match=warn_message):
        pf.remove_flag("-base1", "base")
    stub_configuration.set_profile("base")
    assert pf.get_flags(stub_configuration, Path()) == ["-base2"]

    # Try removing a flag that's not there. This should not
    # cause any issues.
    pf.remove_flag("-does-not-exist")
    assert pf.get_flags(stub_configuration, Path()) == ["-base2"]

    pf.add_flags(["-base1", "-base2"])
    warn_message = "Removing managed flag '-base1'."
    with pytest.warns(UserWarning, match=warn_message):
        pf.remove_flag("-base1")
    stub_configuration.set_profile("")
    assert pf.get_flags(stub_configuration) == ["-base2"]


def test_profile_flags_checksum(stub_configuration):
    '''Tests computation of the checksum.'''
    pf = ProfileFlags()
    pf.define_profile("base")
    list_of_flags = ['one', 'two', 'three', 'four']
    pf.add_flags(list_of_flags, "base")
    stub_configuration._profile = "base"
    assert (pf.checksum(stub_configuration, Path()) ==
            string_checksum(str(list_of_flags)))

    # These flags get added to the "" profile, NOT base:
    list_of_flags_new = ["five", "six"]
    pf.add_flags(list_of_flags_new)
    stub_configuration.set_profile("")
    assert (pf.checksum(stub_configuration, Path()) ==
            string_checksum(str(list_of_flags_new)))

    # Test handling when no config is provided:
    assert (pf.checksum(file_path=Path()) ==
            string_checksum(str(list_of_flags_new)))

    # Test handling when no file_path is provided:
    assert (pf.checksum(stub_configuration) ==
            string_checksum(str(list_of_flags_new)))


def test_profile_flags_errors_invalid_profile_name(stub_configuration):
    '''Tests that given undefined profile names will raise
    KeyError in call functions.
    '''
    pf = ProfileFlags()
    pf.define_profile("base")
    with pytest.raises(KeyError) as err:
        pf.define_profile("base")
    assert "Profile 'base' is already defined." in str(err.value)

    with pytest.raises(KeyError) as err:
        pf.add_flags(["-some-flag"], "does not exist")
    assert ("add_flags: Profile 'does not exist' is not defined."
            in str(err.value))

    with pytest.raises(KeyError) as err:
        pf.remove_flag("-some-flag", "does not exist")
    assert ("remove_flag: Profile 'does not exist' is not defined."
            in str(err.value))

    stub_configuration._profile = "does_not_exist"
    with pytest.raises(KeyError) as err:
        pf.checksum(stub_configuration, Path("/some/path"))
    assert ("checksum: Profile 'does_not_exist' is not defined."
            in str(err.value))


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
