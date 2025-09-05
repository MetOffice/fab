##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the compiler implementation.
'''

import pytest

from fab.tools.flags import Flags, ProfileFlags
from fab.util import string_checksum


def test_flags_constructor():
    '''Tests the constructor of Flags.'''
    f1 = Flags()
    assert isinstance(f1, list)

    # pylint: disable-next=use-implicit-booleaness-not-comparison
    assert f1 == []
    f2 = Flags(["a"])
    assert isinstance(f2, list)
    assert f2 == ["a"]


def test_flags_adding():
    '''Tests adding flags.'''
    f1 = Flags()
    # pylint: disable-next=use-implicit-booleaness-not-comparison
    assert f1 == []
    f1.add_flags("-a")
    assert f1 == ["-a"]
    f1.add_flags(["-b", "-c"])
    assert f1 == ["-a", "-b", "-c"]


def test_remove_flags():
    '''Test remove_flags functionality.'''
    flags = Flags()
    flags.remove_flag("-c", False)
    # pylint: disable-next=use-implicit-booleaness-not-comparison
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
    list_of_flags = ['one', 'two', 'three', 'four']
    flags = Flags(list_of_flags)
    assert flags.checksum() == string_checksum(str(list_of_flags))


def test_profile_flags_with_profile():
    '''Tests adding flags.'''
    pf = ProfileFlags()
    pf.define_profile("base")
    assert pf["base"] == []
    pf.add_flags("-base", "base")
    assert pf["base"] == ["-base"]
    pf.add_flags(["-base2", "-base3"], "base")
    assert pf["base"] == ["-base", "-base2", "-base3"]

    # Check that we get an exception if we specify a profile
    # that does not exist
    with pytest.raises(KeyError) as err:
        _ = pf["does_not_exist"]
    assert "Profile 'does_not_exist' is not defined" in str(err.value)


def test_profile_flags_without_profile():
    '''Tests adding flags.'''
    pf = ProfileFlags()
    assert pf[""] == []
    pf.add_flags("-base")
    assert pf[""] == ["-base"]
    pf.add_flags(["-base2", "-base3"])
    assert pf[""] == ["-base", "-base2", "-base3"]

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


def test_profile_flags_inheriting():
    '''Tests adding flags.'''
    pf = ProfileFlags()
    pf.define_profile("base")
    assert pf["base"] == []
    # And there should not be any inherited profile defined:
    assert "base" not in pf._inherit_from

    pf.add_flags("-base", "base")
    assert pf["base"] == ["-base"]

    pf.define_profile("derived", "base")
    assert pf["derived"] == ["-base"]
    assert pf._inherit_from["derived"] == "base"
    pf.add_flags("-derived", "derived")
    assert pf["derived"] == ["-base", "-derived"]

    pf.define_profile("derived2", "derived")
    assert pf["derived2"] == ["-base", "-derived"]
    pf.add_flags("-derived2", "derived2")
    assert pf["derived2"] == ["-base", "-derived", "-derived2"]


def test_profile_flags_removing():
    '''Tests adding flags.'''
    pf = ProfileFlags()
    pf.define_profile("base")
    assert pf["base"] == []
    pf.add_flags(["-base1", "-base2"], "base")
    warn_message = "Removing managed flag '-base1'."
    with pytest.warns(UserWarning, match=warn_message):
        pf.remove_flag("-base1", "base")
    assert pf["base"] == ["-base2"]

    # Try removing a flag that's not there. This should not
    # cause any issues.
    pf.remove_flag("-does-not-exist")
    assert pf["base"] == ["-base2"]

    pf.add_flags(["-base1", "-base2"])
    warn_message = "Removing managed flag '-base1'."
    with pytest.warns(UserWarning, match=warn_message):
        pf.remove_flag("-base1")
    assert pf[""] == ["-base2"]


def test_profile_flags_checksum():
    '''Tests computation of the checksum.'''
    pf = ProfileFlags()
    pf.define_profile("base")
    list_of_flags = ['one', 'two', 'three', 'four']
    pf.add_flags(list_of_flags, "base")
    assert pf.checksum("base") == string_checksum(str(list_of_flags))

    list_of_flags_new = ['one', 'two', 'three', 'four', "five"]
    pf.add_flags(list_of_flags_new)
    assert pf.checksum() == string_checksum(str(list_of_flags_new))


def test_profile_flags_errors_invalid_profile_name():
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

    with pytest.raises(KeyError) as err:
        pf.checksum("does not exist")
    assert ("checksum: Profile 'does not exist' is not defined."
            in str(err.value))
