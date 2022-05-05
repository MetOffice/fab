##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import os
from pathlib import Path

from fab.builder import Build
from fab.config import Config
from fab.steps.grab import GrabFcm


def jules_source():

    # default to 22411, release 6.3, feb 28 2022
    revision = os.getenv('JULES_REVISION') or "22411"
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / 'jules'

    return Config(
        label='Jules Source',
        workspace=workspace,
        steps=[
            GrabFcm(src=f'fcm:jules.xm_tr/src@{revision}', dst_label='src'),
            GrabFcm(src=f'fcm:jules.xm_tr/utils@{revision}', dst_label='utils'),
        ]
    )


if __name__ == '__main__':
    config = jules_source()
    Build(config=config).run()
