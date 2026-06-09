##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Tests ToolsWithFlags
"""

from pathlib import Path

from fab.tools.category import Category
from fab.tools.flags import ProfileFlags
from fab.tools.tool_with_flags import ToolWithFlags

Category.add("CATEGORY_FOR_UNIT_TESTS")


def test_tool_with_flags_constructor(stub_configuration) -> None:
    """
    Tests construction from argument list.
    """
    tool = ToolWithFlags("gnu", "gfortran", Category.FORTRAN_COMPILER)
    assert isinstance(tool._flags, ProfileFlags)
    # pylint: disable=use-implicit-booleaness-not-comparison
    assert tool.get_flags(stub_configuration, Path()) == []


def test_tool_with_flags_no_profile(stub_configuration) -> None:
    """
    Test that flags without using a profile work as expected.
    """
    tool = ToolWithFlags("some tool", "stool",
                         Category.CATEGORY_FOR_UNIT_TESTS)
    # pylint: disable=use-implicit-booleaness-not-comparison
    assert tool.get_flags(stub_configuration, Path()) == []
    tool.add_flags("-a")
    assert tool.get_flags(stub_configuration, Path()) == ["-a"]
    tool.add_flags(["-b", "-c"])
    assert tool.get_flags(stub_configuration, Path()) == ["-a", "-b", "-c"]


def test_tool_with_flags_profiles(stub_configuration) -> None:
    """
    Test that profiles work as expected. These tests use internal
    implementation details of ProfileFlags, but we need to test that the
    exposed flag-related API works as expected
    """

    # pylint: disable=use-implicit-booleaness-not-comparison
    tool = ToolWithFlags("gfortran", "gfortran", Category.FORTRAN_COMPILER)
    # Make sure by default we get ProfileFlags
    assert isinstance(tool._flags, ProfileFlags)
    assert tool.get_flags(stub_configuration) == []

    # Define a profile with no inheritance
    stub_configuration.set_profile("mode1")
    tool.define_profile("mode1")
    assert tool.get_flags(stub_configuration) == []
    tool.add_flags("-flag1", "mode1")
    assert tool.get_flags(stub_configuration) == ["-flag1"]

    # Define a profile with inheritance
    tool.define_profile("mode2", "mode1")
    stub_configuration.set_profile("mode2")
    assert tool.get_flags(stub_configuration) == ["-flag1"]
    tool.add_flags("-flag2", "mode2")
    assert tool.get_flags(stub_configuration) == ["-flag1", "-flag2"]
