# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from unittest.mock import Mock

from pytest import warns

from fab.steps.grab.archive import grab_archive


class TestGrabArchive(object):

    def test(self, tmp_path):
        tar_file = Path(__file__).parent / '../git/tiny_fortran.tar'

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            grab_archive(config=Mock(source_root=tmp_path), src=tar_file)

        assert (tmp_path / 'tiny_fortran/src/my_mod.F90').exists()
