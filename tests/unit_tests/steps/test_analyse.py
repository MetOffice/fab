from pathlib import Path
from typing import Dict, List, Set
from unittest.mock import Mock

from pytest import fixture, warns, raises

from fab.build_config import BuildConfig
from fab.dep_tree import AnalysedDependent
from fab.parse.fortran import AnalysedFortran, FortranParserWorkaround
from fab.steps.analyse import (_add_manual_results, _add_unreferenced_deps,
                               _gen_file_deps, _gen_symbol_table, _parse_files)
from fab.tools.tool_box import ToolBox
from fab.tools.tool_repository import ToolRepository
from fab.util import HashedFile


class Test_gen_symbol_table(object):
    """
    Tests source symbol management.
    """
    @fixture
    def analysed_files(self) -> List[AnalysedDependent]:
        return [AnalysedDependent(fpath=Path('foo.c'),
                                  symbol_defs=['foo_1', 'foo_2'], file_hash=1),
                AnalysedDependent(fpath=Path('bar.c'),
                                  symbol_defs=['bar_1', 'bar_2'], file_hash=2)]

    def test_vanilla(self, analysed_files: List[AnalysedDependent]) -> None:
        """
        Tests symbol table generation.
        """
        result = _gen_symbol_table(analysed_files=analysed_files)

        assert result == {
            'foo_1': Path('foo.c'),
            'foo_2': Path('foo.c'),
            'bar_1': Path('bar.c'),
            'bar_2': Path('bar.c'),
        }

    def test_duplicate_symbol(self,
                              analysed_files: List[AnalysedDependent]) -> None:
        """
        Tests duplicate symbols in different files.
        """
        analysed_files[1].symbol_defs.add('foo_1')

        with raises(ValueError):
            result = _gen_symbol_table(analysed_files=analysed_files)
            assert result == {
                'foo_1': Path('foo.c'),
                'foo_2': Path('foo.c'),
                'bar_1': Path('bar.c'),
                'bar_2': Path('bar.c'),
                }


class Test_gen_file_deps(object):
    """
    Tests file dpendency management.
    """
    def test_vanilla(self) -> None:
        """
        Tests analysing files.

        ToDo: Messing with "private" state.
        """
        my_file = Path('my_file.f90')
        symbols = {
            'my_mod': my_file,
            'my_func': my_file,
            'dep1_mod': Path('dep1_mod.f90'),
            'dep2': Path('dep2.c'),
        }

        analysed_files = [
            AnalysedDependent(my_file,
                              3,
                              None,
                              {'my_func', 'dep1_mod', 'dep2'},
                              set())
        ]

        _gen_file_deps(analysed_files=analysed_files, symbols=symbols)

        assert analysed_files[0].file_deps == {symbols['dep1_mod'],
                                               symbols['dep2']}


# todo: this is fortran-ey, move it?
class Test_add_unreferenced_deps(object):
    """
    Tests handling unrefrenced dependencies.
    """
    def test_vanilla(self) -> None:
        """
        Tests

        ToDo: Messing with "private" methods.
        """
        # we analysed the source folder and found these symbols
        symbol_table = {
            "root": Path("root.f90"),
            "root_dep": Path("root_dep.f90"),
            "util": Path("util.f90"),
            "util_dep": Path("util_dep.f90"),
        }

        # we extracted the build tree
        build_tree: Dict[Path, AnalysedDependent] = {
            Path('root.f90'): AnalysedFortran(fpath=Path(), file_hash=1),
            Path('root_dep.f90'): AnalysedFortran(fpath=Path(), file_hash=2),
        }

        # we want to force this symbol into the build (because it's not used
        # via modules)
        unreferenced_deps = ['util']

        # the stuff to add to the build tree will be found in here
        all_analysed_files: Dict[Path, AnalysedDependent] = {
            # root.f90 and root_util.f90 would also be in here but the test
            # doesn't need them
            Path('util.f90'): AnalysedFortran(fpath=Path('util.f90'),
                                              file_deps={Path('util_dep.f90')},
                                              file_hash=3),
            Path('util_dep.f90'): AnalysedFortran(fpath=Path('util_dep.f90'),
                                                  file_hash=4),
        }

        _add_unreferenced_deps(
            unreferenced_deps=unreferenced_deps,
            symbol_table=symbol_table,
            all_analysed_files=all_analysed_files,
            build_tree=build_tree)

        assert Path('util.f90') in build_tree
        assert Path('util_dep.f90') in build_tree

    # todo:
    # def test_duplicate(self):
    #     # ensure warning
    #     pass


class Test_parse_files(object):
    """
    Tests examining a file.

    todo: test the correct artefacts are marked as current for the
          cleanup step.
    todo: this method should be tested a bit more thoroughly.
    """
    def test_exceptions(self, tmp_path: Path,
                        stub_tool_repository: ToolRepository,
                        monkeypatch) -> None:
        """
        Tests exceptions thrown from processing do not halt build.

        ToDo: Do we want this? Shouldn't exceptions stop build?

        ToDo: Messing with "private" methods.
        """
        def raises(*args, **kwargs):
            raise Exception("foo")

        # The warning "deprecated 'DEPENDS ON:' comment found in fortran
        # code" is in "def _parse_files" in "source/steps/analyse.py"
        config = BuildConfig('proj', ToolBox(), fab_workspace=tmp_path)

        monkeypatch.setattr('fab.steps.run_mp', raises)
        with warns(UserWarning, match="deprecated 'DEPENDS ON:'"):
            # the exception should be suppressed (and logged) and this step
            # should run to completion
            _parse_files(config, files=[],
                         fortran_analyser=Mock(),
                         c_analyser=Mock())


class TestAddManualResults:
    """
    Tests user over-ridden results. Covers parser failures.
    """
    def test_vanilla(self, monkeypatch) -> None:
        """
        Tests simple replacement.

        ToDo: Messing with "private" methods.
        """
        workaround = FortranParserWorkaround(fpath=Path('foo.f'),
                                             symbol_defs={'foo', })
        analysed_files: Set[AnalysedDependent] = set()

        monkeypatch.setattr('fab.parse.fortran.file_checksum',
                            lambda x: HashedFile(None, 123))
        with warns(UserWarning,
                   match="SPECIAL MEASURE: "
                         "injecting user-defined analysis results"):
            _add_manual_results(special_measure_analysis_results=[workaround],
                                analysed_files=analysed_files)

        assert analysed_files == {AnalysedFortran(fpath=Path('foo.f'),
                                                  file_hash=123,
                                                  symbol_defs={'foo', })}
