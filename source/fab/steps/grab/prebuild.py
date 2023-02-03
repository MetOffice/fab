# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from typing import Dict

from fab.steps import Step
from fab.steps.grab import call_rsync, logger


class GrabPreBuild(Step):
    """
    Copy the contents of another project's prebuild folder into our local prebuild folder.

    """
    def __init__(self, path, objects=True, allow_fail=False):
        super().__init__(name=f'GrabPreBuild {path}')
        self.src = path
        self.objects = objects
        self.allow_fail = allow_fail

    def run(self, artefact_store: Dict, config):
        dst = config.prebuild_folder
        try:
            res = call_rsync(src=self.src, dst=dst)

            # log the number of files transferred
            to_print = [line for line in res.splitlines() if 'Number of' in line]
            logger.info('\n'.join(to_print))

        except RuntimeError as err:
            msg = f"could not grab pre-build '{self.src}':\n{err}"
            logger.warning(msg)
            if not self.allow_fail:
                raise RuntimeError(msg)
