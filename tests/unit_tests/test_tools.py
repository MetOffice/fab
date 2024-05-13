# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

from fab.tools import flags_checksum


class TestFlagsChecksum():

    def test_vanilla(self):
        # I think this is a poor testing pattern.
        flags = ['one', 'two', 'three', 'four']
        assert flags_checksum(flags) == 3011366051
