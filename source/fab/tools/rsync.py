##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the Rsync class for archiving files.
"""

import os
from pathlib import Path
from typing import List, Union

from fab.tools.categories import Categories
from fab.tools.tool import Tool


class Rsync(Tool):
    '''This is the base class for `rsync`.
    '''

    def __init__(self):
        super().__init__("rsync", "rsync", Categories.RSYNC)

    def check_available(self) -> bool:
        '''
        :returns: whether `rsync` is available or not. We do this by
            requesting the rsync version.
        '''
        try:
            self.run("--version")
        except (RuntimeError, FileNotFoundError):
            return False
        return True

    def execute(self, src: Path,
                dst: Path):
        '''Execute an rsync command from src to dst. It supports
        ~ expansion for src, and makes sure that `src` end with a `/`
        so that rsync does not create a sub-directory.

        :param src: the input path.
        :param dst: destination path.
        '''
        src_str = os.path.expanduser(str(src))
        if not src_str.endswith('/'):
            src_str += '/'

        parameters: List[Union[str, Path]] = [
            '--times', '--links', '--stats', '-ru', src_str, dst]
        return self.run(additional_parameters=parameters)
