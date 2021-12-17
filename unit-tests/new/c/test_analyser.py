from pathlib import Path

from fab.dep_tree import AnalysedFile

from fab.tasks.c import CAnalyser
from fab.util import HashedFile


def test_simple_result(tmp_path):
    fpath = Path("test_analyser.c")
    result = CAnalyser().run(HashedFile(fpath, None))

    expected = AnalysedFile(
        fpath=fpath,
        file_hash=None,
        symbol_deps={'monty_func', 'bar_mod'},
        symbol_defs={'external_sub', 'foo_mod', 'external_func'},
        file_deps=set(),
        mo_commented_file_deps={'some_file.c'},
    )
    assert result == expected
