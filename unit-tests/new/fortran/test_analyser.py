import pytest

from fab.tasks.fortran import FortranAnalyser
from fab.util import HashedFile


def create_fortran_file(folder, content):
    fpath = folder / "tmp.f90"
    fpath.write_text(content)
    return fpath


@pytest.fixture
def simple_fortran():
    return """
           module foo_mod
           USE bar_mod, ONLY: foo
!          DEPENDS ON: monty_file
           end module foo_mod
           """


def test_simple_result(tmp_path, simple_fortran):
    fpath = create_fortran_file(tmp_path, simple_fortran)
    result = FortranAnalyser().run(HashedFile(fpath, None))

    assert not isinstance(result, Exception)
    assert result.symbol_defs == {"foo_mod"}
    assert result.symbol_deps == {"bar_mod"}
    assert result.file_deps == {"monty_file.f90"}


# todo:
#  - indented depend comment
