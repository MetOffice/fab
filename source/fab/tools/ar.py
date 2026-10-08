##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the Ar class for archiving files."""

from __future__ import annotations

from pathlib import Path

from fab.tools.category import Category
from fab.tools.tool import Tool


class Ar(Tool):
    """This is the base class for `ar`."""

    Category.add("AR")

    def __init__(self):
        super().__init__("ar", "ar", Category.AR)

    def create(self, output_fpath: Path, members: list[Path | str]):
        """Create the archive with the specified name, containing the
        listed members.

        :param output_fpath: the output path.
        :param members: the list of objects to be added to the archive.
        """
        # Explicit type is required to avoid mypy errors :(
        output_fpath.unlink(missing_ok=True)
        parameters: list[Path | str] = ["cr", output_fpath]
        parameters.extend(map(str, members))
        return self.run(additional_parameters=parameters)
