# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from fab.steps import step
from fab.steps.grab import call_rsync, logger


@step
def grab_pre_build(config, path, objects=True, allow_fail=False):
    """
    Copy the contents of another project's prebuild folder into our local prebuild folder.

    """
    dst = config.prebuild_folder
    try:
        res = call_rsync(src=path, dst=dst)

        # log the number of files transferred
        to_print = [line for line in res.splitlines() if 'Number of' in line]
        logger.info('\n'.join(to_print))

    except RuntimeError as err:
        msg = f"could not grab pre-build '{path}':\n{err}"
        logger.warning(msg)
        if not allow_fail:
            raise RuntimeError(msg)
