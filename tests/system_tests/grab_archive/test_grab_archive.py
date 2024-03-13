# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from unittest import mock

from fab.steps.grab.archive import grab_archive

import pytest


class TestGrabArchive(object):

    def test(self, tmp_path):
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            tar_file = Path(__file__).parent / '../git/tiny_fortran.tar'
            grab_archive(config=mock.Mock(source_root=tmp_path), src=tar_file)

            assert (tmp_path / 'tiny_fortran/src/my_mod.F90').exists()
