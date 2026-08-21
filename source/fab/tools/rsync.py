##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the Rsync class for synchronising file trees.
"""

from pathlib import Path
from typing import Union

from fab.tools.category import Category
from fab.tools.tool import Tool


class Rsync(Tool):
    '''This is the base class for `rsync`.
    '''

    Category.add("RSYNC")

    def __init__(self):
        super().__init__("rsync", "rsync", Category.RSYNC)

    def execute(self, src: Path,
                dst: Path) -> str:
        '''Execute an rsync command from src to dst. It supports
        ~ expansion for src, and makes sure that `src` end with a `/`
        if src is a directory so that rsync does not create a sub-directory.

        :param src: the input path.
        :param dst: destination path.
        '''
        src_abs = src.expanduser().resolve()
        if src_abs.is_dir():
            # Ensure that a directory name ends with a '/'
            src_str = f"{src_abs}/"
        else:
            src_str = str(src_abs)

        # Note that run will change Path to str internally
        parameters: list[Union[str, Path]] = [
            '--times', '--links', '--stats', '-ru', src_str, dst]
        return self.run(additional_parameters=parameters)
