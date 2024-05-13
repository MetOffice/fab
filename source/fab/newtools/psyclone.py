##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file the tool class for PSyclone.

"""

from pathlib import Path
from typing import List, Optional, Union

from fab.newtools.categories import Categories
from fab.newtools.tool import Tool


class Psyclone(Tool):
    '''This is the base class for `PSyclone`.
    '''

    def __init__(self):
        super().__init__("psyclone", "psyclone", Categories.PSYCLONE)

    def check_available(self):
        '''Checks if psyclone is available. We do this by requesting the
        psyclone version.
        '''
        try:
            self.run("--version")
        except (RuntimeError, FileNotFoundError):
            return False
        return True

    def process(self, api: str,
                x90_file: Union[Path, str],
                psy_file: Union[Path, str],
                alg_file: Union[Path, str],
                transformation_script: Optional[Union[Path, str]] = None,
                additional_parameters: Optional[List[str]] = None,
                kernel_roots: Optional[List[str]] = None,
                ):
        '''Create the archive with the specified name, containing the
        listed members.
        :param output_fpath: the output path.
        :param members: the list of objects to be added to the archive.
        '''
        parameters = ["-api", api, "-l", "all",
                      "-opsy", str(psy_file),
                      "-oalg", str(alg_file)]
        if transformation_script:
            parameters.extend(["-s", str(transformation_script)])
        if additional_parameters:
            parameters.extend(additional_parameters)
        if kernel_roots:
            roots_with_dash_d = sum([['-d', str(k)] for k in kernel_roots], [])
            parameters.extend(roots_with_dash_d)
        parameters.append(str(x90_file))
        print("XX", parameters)
        return self.run(additional_parameters=parameters)
