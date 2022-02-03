from pathlib import Path

from fab.constants import BUILD_SOURCE

from fab.config import AddFlags


class TestAddFlags(object):

    def test_constructor(self):
        AddFlags.workspace = Path("/workspace")
        add_flags = AddFlags(match="$source/foo/*", flags=[])
        assert add_flags.match == f"/workspace/{BUILD_SOURCE}/foo/*"

    def test_run(self):
        AddFlags.workspace = Path("/workspace")
        add_flags = AddFlags(match="$source/foo/*", flags=['-I', '$relative/include'])

        my_flags = ["-foo"]
        add_flags.run(fpath=Path(f"/workspace/{BUILD_SOURCE}/foo/bar.c"), flags=my_flags)
        assert my_flags == ['-foo', '-I', f'/workspace/{BUILD_SOURCE}/foo/include']

        my_flags = ["-foo"]
        add_flags.run(fpath=Path(f"/workspace/{BUILD_SOURCE}/bar/bar.c"), flags=my_flags)
        assert my_flags == ['-foo']
