from pathlib import Path
from unittest import mock
from unittest.mock import Mock

from fab.tasks.fortran import FortranCompiler


class Test_run(object):

    def test_vanilla(self):
        # ensure the command is formed correctly
        mock_flags_config = Mock()
        mock_flags_config.flags_for_path.return_value = ['-I', 'foo/bar', '-Dhello']
        c_compiler = FortranCompiler(compiler=['gfortran', '-c'], flags=mock_flags_config)

        analysed_file = Mock(fpath=Path("foo.f90"))

        with mock.patch('fab.tasks.fortran.run_command') as mock_run:
            c_compiler.run(analysed_file)
            mock_run.assert_called_with(['gfortran', '-c', '-I', 'foo/bar', '-Dhello', 'foo.f90', '-o', 'foo.o'])
