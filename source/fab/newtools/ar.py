##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any preprocessor, and two derived
classes for cpp and fpp.

"""

from pathlib import Path
from typing import List, Union

from fab.newtools.categories import Categories
from fab.newtools.tool import Tool


class Ar(Tool):
    '''This is the base class for `ar`.
    '''

    def __init__(self):
        super().__init__("ar", "ar", Categories.AR)

    def check_available(self):
        '''Checks if the compiler is available. We do this by requesting the
        compiler version.
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
        print("XX", type(members), type(map(str, members)))
        parameters = ["cr", str(output_fpath)]
        parameters.extend(map(str, members))
        return self.run(additional_parameters=parameters)
