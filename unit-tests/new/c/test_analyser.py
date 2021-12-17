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
        symbol_deps={'usr_var', 'usr_func'},
        symbol_defs={'func_decl', 'func_def', 'var_def', 'var_extern_def', 'main'},
        file_deps=set(),
        mo_commented_file_deps=set(),
    )
    assert result == expected
