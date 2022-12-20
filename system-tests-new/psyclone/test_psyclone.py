# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import shutil
from pathlib import Path

from fab.steps.psyclone import make_compliant_x90


def test_make_compliant_x90(tmp_path):
    grab_x90_path = Path(__file__).parent / 'sample.compliant_x90'
    input_x90_path = tmp_path / grab_x90_path.name
    shutil.copy(grab_x90_path, input_x90_path)

    result = make_compliant_x90(input_x90_path)
    print('1n', result)

    # compliant_x90_path, removed_names = make_compliant_x90(input_x90_path)
    # print('\n', compliant_x90_path)
    # print(removed_names)
