##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
A step for running multiple files through a command line tool using multiprocessing.

"""
from typing import Dict, List

from fab.build_config import FlagsConfig, AddFlags

from fab.steps import Step


# Initial motivation: unify constructors for preprocessors and compilers as they were already diverging.
class MpExeStep(Step):
    """
    Base class which handles the config for common flags and path filtered flags, for mp steps.

    """

    def __init__(self, exe, common_flags: List[str] = None, path_flags: List[AddFlags] = None, name: str = "mp exe"):
        super().__init__(name)
        self.exe = exe
        self.flags = FlagsConfig(common_flags=common_flags, path_flags=path_flags)

    # todo: can we do more up in this superclass?
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)
