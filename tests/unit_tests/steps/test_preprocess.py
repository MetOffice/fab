# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from unittest import mock

from fab.build_config import BuildConfig
from fab.steps.preprocess import preprocess_fortran
from fab.tools import ToolBox


class Test_preprocess_fortran(object):

    def test_big_little(self, tmp_path):
        # ensure big F90s are preprocessed and little f90s are copied

        config = BuildConfig('proj', ToolBox(), fab_workspace=tmp_path)
        big_f90 = Path(config.source_root / 'big.F90')
        little_f90 = Path(config.source_root / 'little.f90')

        def source_getter(artefact_store):
            return [big_f90, little_f90]

        with mock.patch('fab.steps.preprocess.pre_processor') as mock_pp:
            with mock.patch('shutil.copyfile') as mock_copy:
                with config:
                    preprocess_fortran(config=config, source=source_getter)

        mock_pp.assert_called_once_with(
            config,
            preprocessor=mock.ANY,
            common_flags=mock.ANY,
            files=[big_f90],
            output_collection=mock.ANY,
            output_suffix='.f90',
            name='preprocess fortran',
        )

        mock_copy.assert_called_once_with(str(little_f90), mock.ANY)
