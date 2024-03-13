from pathlib import Path
from unittest import mock

import pytest

from fab.build_config import BuildConfig
from fab.dep_tree import AnalysedDependent
from fab.parse.fortran import AnalysedFortran, FortranParserWorkaround
from fab.steps.analyse import _add_manual_results, _add_unreferenced_deps, _gen_file_deps, _gen_symbol_table, \
    _parse_files
from fab.util import HashedFile


class Test_gen_symbol_table(object):

    @pytest.fixture
    def analysed_files(self):
        return [AnalysedDependent(fpath=Path('foo.c'), symbol_defs=['foo_1', 'foo_2'], file_hash=0),
                AnalysedDependent(fpath=Path('bar.c'), symbol_defs=['bar_1', 'bar_2'], file_hash=0)]

    def test_vanilla(self, analysed_files):
        result = _gen_symbol_table(analysed_files=analysed_files)

        assert result == {
            'foo_1': Path('foo.c'),
            'foo_2': Path('foo.c'),
            'bar_1': Path('bar.c'),
            'bar_2': Path('bar.c'),
        }

    def test_duplicate_symbol(self, analysed_files):
        # duplicate a symbol from the first file in the second file
        analysed_files[1].symbol_defs.add('foo_1')

        with pytest.warns(UserWarning):
            result = _gen_symbol_table(analysed_files=analysed_files)

        assert result == {
            'foo_1': Path('foo.c'),
            'foo_2': Path('foo.c'),
            'bar_1': Path('bar.c'),
            'bar_2': Path('bar.c'),
        }


class Test_gen_file_deps(object):

    def test_vanilla(self):

        my_file = Path('my_file.f90')
        symbols = {
            'my_mod': my_file,
            'my_func': my_file,
            'dep1_mod': Path('dep1_mod.f90'),
            'dep2': Path('dep2.c'),
        }

        analysed_files = [
            mock.Mock(
                spec=AnalysedDependent, fpath=my_file, symbol_deps={'my_func', 'dep1_mod', 'dep2'}, file_deps=set()),
        ]

        _gen_file_deps(analysed_files=analysed_files, symbols=symbols)

        assert analysed_files[0].file_deps == {symbols['dep1_mod'], symbols['dep2']}


# todo: this is fortran-ey, move it?
class Test_add_unreferenced_deps(object):

    def test_vanilla(self):
        # analyser = Analyse(root_symbol=None)

        # we analysed the source folder and found these symbols
        symbol_table = {
            "root": Path("root.f90"),
            "root_dep": Path("root_dep.f90"),
            "util": Path("util.f90"),
            "util_dep": Path("util_dep.f90"),
        }

        # we extracted the build tree
        build_tree = {
            Path('root.f90'): AnalysedFortran(fpath=Path(), file_hash=0),
            Path('root_dep.f90'): AnalysedFortran(fpath=Path(), file_hash=0),
        }

        # we want to force this symbol into the build (because it's not used via modules)
        unreferenced_deps = ['util']

        # the stuff to add to the build tree will be found in here
        all_analysed_files = {
            # root.f90 and root_util.f90 would also be in here but the test doesn't need them
            Path('util.f90'): AnalysedFortran(fpath=Path('util.f90'), file_deps={Path('util_dep.f90')}, file_hash=0),
            Path('util_dep.f90'): AnalysedFortran(fpath=Path('util_dep.f90'), file_hash=0),
        }

        _add_unreferenced_deps(
            unreferenced_deps=unreferenced_deps,
            symbol_table=symbol_table, all_analysed_files=all_analysed_files, build_tree=build_tree)

        assert Path('util.f90') in build_tree
        assert Path('util_dep.f90') in build_tree

    # todo:
    # def test_duplicate(self):
    #     # ensure warning
    #     pass


class Test_parse_files(object):

    # todo: test the correct artefacts are marked as current for the cleanup step
    # todo: this method should be tested a bit more thoroughly

    def test_exceptions(self, tmp_path):
        # make sure parse exceptions do not stop the build
        with mock.patch('fab.steps.run_mp', return_value=[(Exception('foo'), None)]), \
             pytest.warns(UserWarning, match="deprecated 'DEPENDS ON:'"):
            # The warning "deprecated 'DEPENDS ON:' comment found in fortran code"
            # is in "def _parse_files" in "source/steps/analyse.py"
            config = BuildConfig('proj', fab_workspace=tmp_path)

            # the exception should be suppressed (and logged) and this step should run to completion
            _parse_files(config, files=[], fortran_analyser=mock.Mock(), c_analyser=mock.Mock())


class Test_add_manual_results(object):
    # test user-specified analysis results, for when fparser fails to parse a valid file.

    def test_vanilla(self):
        # test normal usage of manual analysis results
        workaround = FortranParserWorkaround(fpath=Path('foo.f'), symbol_defs={'foo', })
        analysed_files = set()

        with mock.patch('fab.parse.fortran.file_checksum', return_value=HashedFile(None, 123)), \
             pytest.warns(UserWarning, match="SPECIAL MEASURE: injecting user-defined analysis results"):
            # This warning "UserWarning: SPECIAL MEASURE: injecting user-defined analysis results"
            # is in "def _add_manual_results" in "source/steps/analyse.py"
            _add_manual_results(special_measure_analysis_results=[workaround], analysed_files=analysed_files)

        assert analysed_files == {AnalysedFortran(fpath=Path('foo.f'), file_hash=123, symbol_defs={'foo', })}
