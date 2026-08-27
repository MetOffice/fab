##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the compiler implementation.
'''

from pathlib import Path
import pytest

from fab.tools.flags import AlwaysFlags
from fab.tools.profile_flags import ProfileFlags
from fab.util import string_checksum


def test_profile_flags_defining_profiles():
    """
    Tests defining profiles.
    """
    assert ProfileFlags._inherit_from == {'': ''}
    ProfileFlags.define_profile("base")
    assert ProfileFlags._inherit_from == {'base': '', '': ''}

    ProfileFlags.define_profile("derived", inherit_from="base")
    assert ProfileFlags._inherit_from == {'': '',
                                          'base': '',
                                          'derived': 'base'}

    # Creating an instance of ProfileFlags will add a profile
    # inheriting from "".
    ProfileFlags(profile="new_profile")
    assert ProfileFlags._inherit_from == {'': '',
                                          'base': '',
                                          'derived': 'base',
                                          'new_profile': ''}

    pr1 = ProfileFlags(profile="another_profile", flags="-flag")
    # This will have added a single AlwaysFlag instance, on which
    # we call get_flags:
    assert pr1["another_profile"][0].get_flags() == ["-flag"]

    # Trying to create an already existing profile should raise an error:
    with pytest.raises(KeyError) as err:
        ProfileFlags.define_profile('base')
    assert "Profile 'base' is already defined" in str(err.value)

    # Inheriting from a non-existing profile should raise an error:
    with pytest.raises(KeyError) as err:
        ProfileFlags.define_profile("new", inherit_from="does_not_exist")
    assert ("Inherited profile 'does_not_exist' is not defined"
            in str(err.value))

    # Check that we get an exception if we specify a profile
    # that does not exist in __get_item__
    pf = ProfileFlags()
    with pytest.raises(KeyError) as err:
        _ = pf["does_not_exist"]
    assert "Profile 'does_not_exist' is not defined" in str(err.value)


def test_profile_flags_inheritance(stub_configuration):
    """
    Tests adding flags.
    """
    ProfileFlags.define_profile("base")
    ProfileFlags.define_profile("derived", inherit_from="base")
    pf = ProfileFlags()
    # First test that we can access all profiles in the instance:
    assert pf[""] == []
    assert pf["base"] == []
    assert pf["derived"] == []

    # Now add flags to the various profiles
    pf.add_flags("-dummy")
    stub_configuration.set_profile("derived")
    assert pf.get_flags(stub_configuration) == ["-dummy"]
    pf.add_flags("-base", profile="base")
    assert pf.get_flags(stub_configuration) == ["-dummy", "-base"]
    pf.add_flags("-derived", profile="derived")
    assert pf.get_flags(stub_configuration) == ["-dummy", "-base", "-derived"]

    # And ensure that inherited profiles do not get the flags
    # from derived profiles>
    stub_configuration.set_profile("")
    assert pf.get_flags(stub_configuration) == ["-dummy"]
    stub_configuration.set_profile("base")
    assert pf.get_flags(stub_configuration) == ["-dummy", "-base"]


def test_profile_flags_several_flags():
    """
    Test that adding several flags for the same profile will
    add more AlwaysFlags instances
    """

    ProfileFlags.define_profile("base")
    pf = ProfileFlags()
    pf.add_flags("-base", profile="base")

    assert len(pf["base"]) == 1
    assert isinstance(pf["base"][0], AlwaysFlags)
    assert pf["base"][0].get_flags() == ["-base"]

    pf.add_flags(["-base2", "-base3"], "base")
    assert len(pf["base"]) == 2
    assert isinstance(pf["base"][0], AlwaysFlags)
    assert isinstance(pf["base"][1], AlwaysFlags)
    assert pf["base"][0].get_flags() == ["-base"]
    assert pf["base"][1].get_flags() == ["-base2", "-base3"]


def test_profile_flags_without_profile():
    """
    Tests adding flags when using the default "" profile.
    """
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


def test_profile_flags_removing(stub_configuration):
    """
    Tests removing flags.
    """
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

    # Remove a single flag, even if it was added in the same add_flags
    # call with other flags
    pf.add_flags(["-base1", "-base2"])
    warn_message = "Removing managed flag '-base1'."
    with pytest.warns(UserWarning, match=warn_message):
        pf.remove_flag("-base1")
    stub_configuration.set_profile("")
    assert pf.get_flags(stub_configuration) == ["-base2"]

    # Trying to remove flag from a non-existing profile:
    with pytest.raises(KeyError) as err:
        pf.remove_flag("-some-flag", "does not exist")
    assert ("remove_flag: Profile 'does not exist' is not defined."
            in str(err.value))


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

    # Test checksum from a non-existing profile
    stub_configuration._profile = "does_not_exist"
    with pytest.raises(KeyError) as err:
        pf.checksum(stub_configuration, Path("/some/path"))
    assert ("checksum: Profile 'does_not_exist' is not defined."
            in str(err.value))


def test_profile_flags_errors_invalid_profile_name():
    '''Tests that given undefined profile names will raise
    KeyError in call functions.
    '''
    pf = ProfileFlags()
    pf.define_profile("base")

    with pytest.raises(KeyError) as err:
        pf.add_flags(["-some-flag"], "does not exist")
    assert ("add_flags: Profile 'does not exist' is not defined."
            in str(err.value))
