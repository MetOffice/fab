##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the Ar class for archiving files.
"""

from pathlib import Path
from typing import List, Union

from fab.tools.categories import Categories
from fab.tools.tool import Tool


class Ar(Tool):
    '''This is the base class for `ar`.
    '''

    def __init__(self):
        super().__init__("ar", "ar", Categories.AR)

    def check_available(self):
        '''
        :returns: whether `ar` is available or not. We do this by
            requesting the ar version.
        '''
        try:
            self.run("--version")
        except (RuntimeError, FileNotFoundError):
            return False
        return True

    def create(self, output_fpath: Path,
               members: List[Union[Path, str]]):
        '''Create the archive with the specified name, containing the
        listed members.

        :param output_fpath: the output path.
        :param members: the list of objects to be added to the archive.
        '''
        # Explicit type is required to avoid mypy errors :(
        parameters: List[Union[Path, str]] = ["cr", output_fpath]
        parameters.extend(map(str, members))
        return self.run(additional_parameters=parameters)
