# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from unittest import mock

from fab.steps.grab.archive import GrabArchive


class TestGrabArchive(object):

    def test(self, tmp_path):
        tar_file = Path(__file__).parent / '../git/tiny_fortran.tar'
        grab = GrabArchive(src=tar_file)
        grab.run(artefact_store={}, config=mock.Mock(source_root=tmp_path))

        assert (tmp_path / 'tiny_fortran/src/my_mod.F90').exists()
