##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Descend a directory tree.
"""
from collections import defaultdict
from pathlib import Path
from typing import Iterator, List


def file_walk(path: Path) -> Iterator[Path]:
    assert path.is_dir()

    for i in path.iterdir():
        if i.is_dir():
            yield from file_walk(i)
        else:
            yield i


def get_fpaths_by_type(fpaths: List[Path]):

    fpaths_by_type = defaultdict(list)
    for fpath in fpaths:
        fpaths_by_type[fpath.suffix].append(fpath)

    return fpaths_by_type
