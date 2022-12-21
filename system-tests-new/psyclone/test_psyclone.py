# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import filecmp
import shutil
from pathlib import Path

from fab.parse.fortran import X90Analyser
from fab.steps.psyclone import make_compliant_x90


def test_make_compliant_x90(tmp_path):
    # make non-compliant x90 parsable by removing the name keyword from calls to invoke
    grab_x90_path = Path(__file__).parent / 'sample.non_compliant_x90'
    input_x90_path = tmp_path / grab_x90_path.name
    shutil.copy(grab_x90_path, input_x90_path)

    compliant_x90_path, removed_names = make_compliant_x90(input_x90_path)

    assert removed_names == ['name a', 'name b', 'name c', 'name d', 'name e', 'name f']
    assert filecmp.cmp(compliant_x90_path, Path(__file__).parent / 'sample.compliant_x90')


class TestX90Analyser(object):

    def test_vanilla(self, tmp_path):
        compliant_x90_path = Path(__file__).parent / 'sample.compliant_x90'
        x90_analyser = X90Analyser()
        x90_analyser._prebuild_folder = tmp_path

        x90_analyser.run(compliant_x90_path)


