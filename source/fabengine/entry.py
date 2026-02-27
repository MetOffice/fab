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
from fabengine.work_queue import QueueStrategy


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
        "--profile", action="store_true", help="Harvest performance data for build."
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
        options.work_dir,
        options.jobs,
        options.monitor,
        options.profile,
        options.queue_strategy,
    )
