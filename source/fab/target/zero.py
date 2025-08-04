#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Class which implements a zero-configuration build target.
"""

from argparse import ArgumentParser, Namespace
from pathlib import Path

from .base import FabTargetBase
from ..tools import Category, ToolBox, ToolRepository
from ..build_config import BuildConfig
from ..steps.grab.folder import grab_folder
from ..steps.find_source_files import find_source_files
from ..steps.preprocess import preprocess_fortran
from ..steps.c_pragma_injector import c_pragma_injector
from ..steps.analyse import analyse
from ..steps.compile_fortran import compile_fortran
from ..steps.compile_c import compile_c
from ..steps.link import link_exe


class FabZeroConfig(FabTargetBase):
    """Implementation of a zero-configuration build target."""

    project_name = "zero-config"

    @staticmethod
    def add_arguments(parser: ArgumentParser) -> None:
        """Add zero-config mode command line options.

        Zero configuration requires the name of the directory
        containing the source code.

        :param ArgumentParser parser: an existing command line argument parser.
        """

        parser.add_argument(
            "source", type=Path, nargs="?", default=".", help="source directory"
        )

    @staticmethod
    def check_arguments(parser: ArgumentParser, args: Namespace) -> None:
        """Check the zero-config options for correctness."""

        if not args.source.is_dir():
            parser.error("source must be a valid directory")

    def run(self, args: Namespace) -> None:
        """Build an executable with no previous knowledge.

        Run the zero configuration build target recipe.

        :param Namespace args: instance containing parsed command line arguments.
        """

        project_label = (
            args.project
            if hasattr(args, "project") and args.project
            else self.project_name
        )

        tr = ToolRepository()
        fc = tr.get_default(Category.FORTRAN_COMPILER, mpi=False, openmp=False)
        linker = tr.get_tool(Category.LINKER, f"linker-{fc.name}")

        tool_box = ToolBox()
        tool_box.add_tool(fc)
        tool_box.add_tool(linker)

        with BuildConfig(
            project_label=project_label,
            mpi=False,
            openmp=False,
            tool_box=tool_box,
            fab_workspace=Path(args.workspace),
        ) as config:
            grab_folder(config, args.source)
            find_source_files(config)

            preprocess_fortran(config)
            c_pragma_injector(config)
            analyse(config, find_programs=True)

            compile_fortran(config)
            compile_c(config)
            link_exe(config, flags=[])
