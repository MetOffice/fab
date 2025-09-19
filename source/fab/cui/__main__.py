#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fab command to build and maintain complex software applications.
"""

import sys
from importlib.util import module_from_spec, spec_from_loader
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType
from typing import List, Optional


from .arguments import FabArgumentParser
from ..logtools import make_logger, setup_file_logging
from ..target.base import FabTargetBase
from ..target.zero import FabZeroConfig


# Names of default build recipe class and methods in the FabFile
TARGET_CLASS = "FabBuildTarget"
ARGUMENT_METHOD = "add_arguments"
CHECK_METHOD = "check_arguments"


def import_from_path(module_name: str, file_path: Path) -> Optional[ModuleType]:
    """Load a module by file path."""
    # Temporarily disable bytecode genearation to prevent __pycache__
    # directories from being created in the current working directory
    bytecode_setting = sys.dont_write_bytecode
    sys.dont_write_bytecode = True

    loader = SourceFileLoader(module_name, str(file_path))
    spec = spec_from_loader(module_name, loader)
    if spec is None or spec.loader is None:
        # Unable to find the file for some reason
        return None

    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    # Restore previous bytecode generation setting
    sys.dont_write_bytecode = bytecode_setting
    return module


def main(argv: Optional[List[str]] = None):
    """Main function.

    :param argv: list of command line arguments.  Use sys.argv if not specified.
    """

    if argv is None:
        # Use system argument if none have been provided
        argv = sys.argv

    parser = FabArgumentParser(description=__doc__)
    file_args = parser.parse_fabfile_only(argv)

    if file_args.file is not None:
        builder = import_from_path("builder", file_args.file)
        if builder is None:
            parser.error(f"unable to import {file_args.file}")
        build_class = getattr(builder, TARGET_CLASS, None)
        if build_class is None:
            parser.error(f"unable to find {TARGET_CLASS} in {file_args.file}")
        if not issubclass(build_class, FabTargetBase):
            parser.error(f"{TARGET_CLASS} does not extend FabTargetBase")

    elif file_args.zero_config:
        # There is no --file or FabFile, so use zero config mode
        build_class = FabZeroConfig

    # Allow the build target to add options to the parser
    add_arguments = getattr(build_class, ARGUMENT_METHOD, None)
    if add_arguments is not None:
        add_arguments(parser)

    # Parser the unified command line options
    args = parser.parse_args(argv)

    # Allow the build target to validate the options
    check_arguments = getattr(build_class, CHECK_METHOD, None)
    if check_arguments is not None:
        check_arguments(parser, args)

    if args.project is None:
        # Use the project_name from the class
        args.project = str(getattr(build_class, "project_name"))

    args.project_workspace = args.workspace / args.project
    args.project_workspace.mkdir(parents=True, exist_ok=True)

    # Write log messages to a file
    logger = make_logger("system")
    setup_file_logging(args.project_workspace / "build.log")

    try:
        # Create a build class.  Ignore typing errors about None
        # because the previous checks should have forced an exit
        # via the parser if build_class really is None
        builder = build_class()  # type: ignore[misc]
    except TypeError as error:
        # Report abstract typing errors
        print(f"error: {error}", file=sys.stderr)
        logger.error(str(error))
        raise SystemExit(10)

    try:
        # Run the build process
        builder.run(args)
    except KeyboardInterrupt:
        print("error: interrupted by user", file=sys.stderr)
        logger.error("interrupted by user")
        raise SystemExit(11)


if __name__ == "__main__":

    main()
