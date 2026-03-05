from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_file_location
from inspect import getmembers, isclass
from logging import StreamHandler, getLogger, DEBUG, INFO, WARNING
from pathlib import Path
from sys import argv
from typing import Optional, Sequence

from fabengine.configuration import FabConfiguration
from fabengine.core import fab_core
from fabengine.package import (
    IncludePath,
    LibraryName,
    LinkerArgument,
    LinkerPath,
    Package,
    VariableDefinition,
    CompilerArgument,
)
from fabengine.work_queue import QueueStrategy


def parse_libmap(argument: str) -> Package:
    """
    Converts library mapping specification to object.

    Format of input string is
    <name>:<include dir>,...:<variable>[=<value>],...:<library dir>,...:<library name>,...
    """
    bits = argument.split(":", maxsplit=4)
    assert len(bits) > 0

    cargs: list[CompilerArgument] = []
    try:  # Include paths
        carg_list = bits[1].split(",")
        for carg in carg_list:
            if not carg:
                continue
            carg_path = Path(carg)
            cargs.append(IncludePath(carg_path))
    except IndexError:
        pass

    try:  # Variable definitions
        carg_list = bits[2].split(",")
        for carg in carg_list:
            if not carg:
                continue
            variable_name, _, variable_value = carg.partition("=")
            cargs.append(VariableDefinition(variable_name, variable_value or None))
    except IndexError:
        pass

    largs: list[LinkerArgument] = []
    try:  # Linker paths
        larg_list = bits[3].split(",")
        for larg in larg_list:
            if not larg:
                continue
            larg_path = Path(larg)
            largs.append(LinkerPath(larg_path))
    except IndexError:
        pass

    try:  # Additional libraries
        larg_list = bits[4].split(",")
        for larg in larg_list:
            if not larg:
                continue
            largs.append(LibraryName(larg))
    except IndexError:
        pass

    largs.append(LibraryName(bits[0].strip()))

    return Package(bits[0].strip(), tuple(), cargs, largs)


def command_line(arguments: Optional[Sequence[str]] = None) -> Namespace:
    """
    Parses command line arguments for use by Fab.
    """
    if arguments is None:
        arguments = argv[1:]

    parser = ArgumentParser()
    parser.add_argument(
        "--fabfile",
        "-f",
        type=Path,
        default=Path() / "Fabfile",
        help="Build configuration script file.",
    )
    parser.add_argument(
        "--jobs", "-j", type=int, default=1, help="Number of worker threads to use."
    )
    parser.add_argument(
        "--work-dir",
        "-w",
        type=Path,
        default="work",
        help="Build system scratch space.",
    )
    parser.add_argument(
        "--map-library",
        "-m",
        action="append",
        type=parse_libmap,
        help="<name>:<include dir>,...:<library dir | library name>,...",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Provide running commentary on progress.",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Get really chatty with running commentary.",
    )
    parser.add_argument(
        "--no-monitor",
        dest="monitor",
        action="store_false",
        help="Disable progress monitor.",
    )
    parser.add_argument(
        "--timing-file", type=Path, help="Harvest performance data for build."
    )
    parser.add_argument(
        "--queue-strategy",
        type=lambda s: QueueStrategy[s.upper()],
        choices=QueueStrategy,
        default="always_to_back",
        help="Experiment with queue strategy.",
    )
    options = parser.parse_args(arguments)

    options.level = WARNING
    if options.verbose:
        options.level = INFO
    if options.debug:
        options.level = DEBUG

    return options


def instantiate_configuration(fabfile: Path) -> FabConfiguration:
    """
    Creates an object from the Fabfile.

    .. todo:: Python documentation warns against this form of import.
    """
    if fabfile.name.lower() == "fabfile":
        name = fabfile.parent.name
    elif fabfile.suffix == ".fabfile":
        name = fabfile.stem
    else:
        raise RuntimeError(f"Not sure what module name to give <{fabfile}>")
    name = "fabengine.user." + name.replace(".", "_")  # No full stops in name
    spec = spec_from_file_location(
        name, fabfile, loader=SourceFileLoader(name, str(fabfile))
    )
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

    for cls_name, cls in getmembers(
        module, lambda m: isclass(m) and m.__module__ == name
    ):
        return cls()
    raise RuntimeError("No FabConfiguration class found in Fabfile.")


def cli() -> None:
    """
    Command-line interface for Fab.
    """
    options = command_line()

    logger = getLogger(__package__)
    logger.setLevel(options.level)
    logger.addHandler(StreamHandler())

    configuration = instantiate_configuration(options.fabfile)

    fab_core(
        configuration,
        {package.name: package for package in options.map_library or []},
        options.work_dir,
        options.jobs,
        options.monitor,
        options.queue_strategy,
        options.timing_file,
    )
