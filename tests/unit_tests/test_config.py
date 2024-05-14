from pathlib import Path

from fab.build_config import AddFlags, BuildConfig
from fab.constants import SOURCE_ROOT
from fab.tools import ToolBox


class TestAddFlags(object):

    def test_run(self):
        add_flags = AddFlags(match="$source/foo/*", flags=['-I', '$relative/include'])
        config = BuildConfig('proj', ToolBox(),
                             fab_workspace=Path("/fab_workspace"))

        # anything in $source/foo should get the include folder
        my_flags = ["-foo"]
        add_flags.run(
            fpath=Path(f"/fab_workspace/proj/{SOURCE_ROOT}/foo/bar.c"),
            input_flags=my_flags,
            config=config)
        assert my_flags == ['-foo', '-I', f'/fab_workspace/proj/{SOURCE_ROOT}/foo/include']

        # anything in $source/bar should NOT get the include folder
        my_flags = ["-foo"]
        add_flags.run(
            fpath=Path(f"/workspace/{SOURCE_ROOT}/bar/bar.c"),
            input_flags=my_flags,
            config=config)
        assert my_flags == ['-foo']
