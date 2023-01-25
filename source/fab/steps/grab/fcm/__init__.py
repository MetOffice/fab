# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Union

from fab.tools import run_command


def is_working_copy(dst: Union[str, Path]) -> bool:
    try:
        run_command(['svn', 'info'], cwd=dst)
    except RuntimeError:
        return False
    return True