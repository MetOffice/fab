from typing import Dict

from fab.config import FlagsConfig
from fab.steps import Step


# Initial motivation: unify constructors for preprocessors and compilers as they were already diverging.
class MpExeStep(Step):
    """
    Common base class for steps which call an executable for multiple files, using multiprocessing.

    """
    def __init__(self, exe, common_flags, path_flags, name):
        super().__init__(name)
        self.exe = exe
        self._flags = FlagsConfig(workspace=self.workspace, common_flags=common_flags, all_path_flags=path_flags)

    # todo: can we do more up in this superclass?
    def run(self, artefacts: Dict):
        raise NotImplementedError
