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
!          this is a comment
           module foo_mod
           type :: bar_type
           end type bar_type
           end module foo_mod
           """


def test_um_depend_comment(tmp_path, simple_fortran):
    fpath = create_fortran_file(tmp_path, simple_fortran)
    fan = FortranAnalyser()
    result = fan.run(HashedFile(fpath, None))
    assert not isinstance(result, Exception)
