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

from fabengine.build_script import BuildScript
from fabengine.configuration_tools import WriteOnceDict
from fabengine.core import fab_core
from fabengine.package import (
    IncludePath,
    LibraryName,
    LinkerArgument,
    LinkerPath,
    Package,
    partition_specification,
    pkg_config,
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


def instantiate_build_script(fabfile: Path) -> BuildScript:
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
    # Import class from another python file equivalent
    spec.loader.exec_module(module)

    for cls_name, cls in getmembers(
        module, lambda m: isclass(m) and m.__module__ == name
    ):
        return cls()
    raise RuntimeError("No BuildScript class found in Fabfile.")


def instantiate_script_config(
    build_script: BuildScript,
    work_dir: Path,
    timing_file: Path,
    worker_threads: int,
    monitor: bool,
    queue_strategy: QueueStrategy,
) -> WriteOnceDict:
    """
    Create a script configuration WriteOnceDict containing options affecting the
    behaviour of the build script

    :param build_script: Describes the build.
    :param work_dir: Directory used as scratch space for build.
    :param timing_file: File to receive action timings.
    :param worker_threads: Number of workers to use.
    :param monitor: Run progress monitor.
    :param queue_strategy: Use this when adding actions to queue.
    :return: Script configuration WriteOnceDict
    """

    script_config = build_script.configuration()
    if "paths" not in script_config:
        script_config["paths"] = WriteOnceDict({})
    script_config["paths"]["work_dir"] = work_dir
    script_config["paths"]["work_dir"].mkdir(exist_ok=True)
    script_config["paths"]["build_dir"] = script_config["paths"]["work_dir"] / "build"
    script_config["paths"]["build_dir"].mkdir(exist_ok=True)
    script_config["paths"]["module_dir"] = (
        script_config["paths"]["build_dir"] / "modules"
    )
    script_config["paths"]["module_dir"].mkdir(exist_ok=True)
    script_config["paths"]["performance_file"] = timing_file
    script_config["worker_threads"] = worker_threads
    script_config["monitor"] = monitor
    script_config["queue_strategy"] = queue_strategy
    return script_config


def instantiate_build_config(
    build_script: BuildScript,
    map_library: list[Package],
) -> WriteOnceDict:
    """
    Create a build configuration WriteOnceDict containing options affecting the final
    executable

    :param build_script: Describes the build.
    :param map_library: Library mapping object
    :return: Build configuration WriteOnceDict
    """

    packages: list[Package] = []
    package_table = {package.name: package for package in map_library or []}
    for specification in build_script.libraries():
        package_name, _, _ = partition_specification(specification)
        if package_name in package_table:
            packages.append(package_table[package_name])
        else:  # package_name not in package_table
            packages.append(pkg_config(specification))

    # Todo: Hardwired C++ runtime. Need a proper solution for language runtimes.
    packages.append(Package("stdc++", (), [], [LibraryName("stdc++")]))

    fpp_definitions = build_script.fpp_definitions()

    return WriteOnceDict(
        {
            "fpp_definitions": fpp_definitions,
            "fc_ignore_modules": [
                "funit",
                "pfunit",  # pFUnit
                "mpi",
                "mpi_f08",  # MPI
                "netcdf",  # NetCDF
                "omp_lib",  # OpenMP
                "xios",
                "icontext",
                "mod_wait",
                "mod_oasis",  # XIOS/OASIS
                "yaxt",  # YAXT
                "vernier_mod",  # Vernier
                "c_shum_byteswap",  # ShUMlib
            ],
            "field_instances": [
                {"real": "real32"},
                {"real": "real64"},
                {"integer": "int32"},
            ],
            "build_tags": {"um": ["-fdefault-real-8", "-fdefault-double-8"]},
            "tag_dirs": {
                "casim/": ["um"],
                "jules/": ["um"],
                "physics_schemes/": ["um"],
                "physics_schemes_interface/legacy/": ["um"],
                "socrates/": ["um"],
                "ukca/": ["um"],
            },
            "inclusion_suffixes": [".h", ".inc"],
            "packages": tuple(packages),
            "repositories": build_script.repositories(),
        }
    )


def cli() -> None:
    """
    Command-line interface for Fab.
    """
    options = command_line()

    logger = getLogger(__package__)
    logger.setLevel(options.level)
    logger.addHandler(StreamHandler())

    build_script = instantiate_build_script(options.fabfile)
    script_config = instantiate_script_config(
        build_script,
        options.work_dir,
        options.timing_file,
        options.jobs,
        options.monitor,
        options.queue_strategy,
    )
    build_config = instantiate_build_config(build_script, options.map_library)

    fab_core(
        script_config,
        build_config,
    )
