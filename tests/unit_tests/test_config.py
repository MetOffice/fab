from pathlib import Path

from fab.config import AddFlags
from fab.constants import SOURCE_ROOT


class TestAddFlags(object):

    def test_run(self):
        workspace = Path("/workspace")
        add_flags = AddFlags(match="$source/foo/*", flags=['-I', '$relative/include'])

        my_flags = ["-foo"]
        add_flags.run(fpath=Path(f"/workspace/{SOURCE_ROOT}/foo/bar.c"), input_flags=my_flags, workspace=workspace)
        assert my_flags == ['-foo', '-I', f'/workspace/{SOURCE_ROOT}/foo/include']

        my_flags = ["-foo"]
        add_flags.run(fpath=Path(f"/workspace/{SOURCE_ROOT}/bar/bar.c"), input_flags=my_flags, workspace=workspace)
        assert my_flags == ['-foo']
