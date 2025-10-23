##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Test the mo.py file, which handles 'DEPENDS ON' dependency comments.
"""

import logging
from pathlib import Path

from fab.mo import add_mo_commented_file_deps
from fab.parse.c import AnalysedC
from fab.parse.fortran import AnalysedFortran


def test_mo():
    """Test that a commented dependency is added. This especially
    tests that a dependency that is specified as '.o', is added
    as a dependency as the corresponding '.c' file.
    """
    src_tree = {
        Path('foo.f90'): AnalysedFortran(fpath=Path('foo.f90'),
                                         file_hash=0,
                                         mo_commented_file_deps=["root.o"]),
        Path('root.c'): AnalysedC(fpath=Path('/some/path/root.c'),
                                  file_hash=0),
    }
    an_for = src_tree[Path('foo.f90')]
    assert an_for.file_deps == set()
    add_mo_commented_file_deps(src_tree)
    assert an_for.file_deps == set([Path('/some/path/root.c')])


def test_mo_missing_ignored():
    """Test handling of a missing dependency if it is supposed to be ignored.
    """
    src_tree = {
        Path('foo.f90'): AnalysedFortran(fpath=Path('foo.f90'),
                                         file_hash=0,
                                         mo_commented_file_deps=["root.o"]),
    }
    an_for = src_tree[Path('foo.f90')]
    assert an_for.file_deps == set()
    add_mo_commented_file_deps(src_tree,
                               ignore_dependencies=["root.o"])
    assert an_for.file_deps == set()

    # Now also check that the ignore list can use the .c name:
    add_mo_commented_file_deps(src_tree,
                               ignore_dependencies=["root.c"])
    assert an_for.file_deps == set()


def test_mo_missing_warning(caplog):
    """Test handling of a missing dependency if no ignore is defined
    for it.
    """
    src_tree = {
        Path('foo.f90'): AnalysedFortran(fpath=Path('foo.f90'),
                                         file_hash=0,
                                         mo_commented_file_deps=["root.o"]),
    }
    an_for = src_tree[Path('foo.f90')]
    assert an_for.file_deps == set()
    with caplog.at_level(logging.ERROR):
        add_mo_commented_file_deps(src_tree)
    # There should be one error logged:
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR"

    assert an_for.file_deps == set()
