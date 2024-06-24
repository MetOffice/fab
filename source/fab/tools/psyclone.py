##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the tool class for PSyclone.
"""

from pathlib import Path
from typing import Callable, List, Optional, TYPE_CHECKING, Union

from fab.tools.category import Category
from fab.tools.tool import Tool

if TYPE_CHECKING:
    # TODO 314: see if this circular dependency can be broken
    # Otherwise we have a circular dependency:
    # BuildConfig needs ToolBox which imports __init__ which imports this
    from fab.build_config import BuildConfig


class Psyclone(Tool):
    '''This is the base class for `PSyclone`.
    '''

    def __init__(self):
        super().__init__("psyclone", "psyclone", Category.PSYCLONE)

    def process(self, api: str,
                config: "BuildConfig",
                x90_file: Path,
                psy_file: Path,
                alg_file: Union[Path, str],
                transformation_script: Optional[Callable[[Path, "BuildConfig"],
                                                         Path]] = None,
                additional_parameters: Optional[List[str]] = None,
                kernel_roots: Optional[List[Union[str, Path]]] = None
                ):
        # pylint: disable=too-many-arguments
        '''Run PSyclone with the specified parameters.

        :param api: the PSyclone API.
        :param x90_file: the input file for PSyclone
        :param psy_file: the output PSy-layer file.
        :param alg_file: the output modified algorithm file.
        :param transformation_script: an optional transformation script
        :param additional_parameters: optional additional parameters
            for PSyclone
        :param kernel_roots: optional directories with kernels.
        '''

        parameters: List[Union[str, Path]] = [
            "-api", api, "-l", "all", "-opsy", psy_file, "-oalg", alg_file]
        if transformation_script:
            transformation_script_return_path = \
                transformation_script(x90_file, config)
            if transformation_script_return_path:
                parameters.extend(['-s', transformation_script_return_path])

        if additional_parameters:
            parameters.extend(additional_parameters)
        if kernel_roots:
            roots_with_dash_d: List[str] = sum([['-d', str(k)]
                                                for k in kernel_roots], [])
            parameters.extend(roots_with_dash_d)
        parameters.append(str(x90_file))
        return self.run(additional_parameters=parameters)
