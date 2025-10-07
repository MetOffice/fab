##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the Ar class for archiving files.
"""

from pathlib import Path
from typing import List, Union

from fab.tools.category import Category
from fab.tools.tool import Tool


class Ar(Tool):
    '''This is the base class for `ar`.
    '''

    def __init__(self):
        super().__init__("ar", "ar", Category.AR)

    def create(self, output_fpath: Path,
               members: List[Union[Path, str]]):
        '''Create the archive with the specified name, containing the
        listed members.

        :param output_fpath: the output path.
        :param members: the list of objects to be added to the archive.
        '''
        # Explicit type is required to avoid mypy errors :(
        output_fpath.unlink(missing_ok=True)
        parameters: List[Union[Path, str]] = ["cr", output_fpath]
        parameters.extend(map(str, members))
        return self.run(additional_parameters=parameters)
