from pathlib import Path

from fab.tasks.fortran import FortranAnalyser
from fab.util import HashedFile


def create_fortran_file(folder, content):
    fpath = folder / "tmp.f90"
    fpath.write_text(content)
    return fpath


# todo: test function binding
def test_simple_result(tmp_path):
    result = FortranAnalyser().run(HashedFile(Path("test_analyser.f90"), None))

    assert not isinstance(result, Exception)
    assert result.symbol_defs == {"foo_mod"}
    assert result.symbol_deps == {"bar_mod"}
    assert result.file_deps == {"some_file.f90"}


# todo:
#  - indented depend comment
