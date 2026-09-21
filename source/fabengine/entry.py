from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_file_location
from inspect import getmembers, isclass
from logging import DEBUG, INFO, WARNING
from pathlib import Path
from sys import argv

from fabengine.build_script import BuildScript
from fabengine.configuration_tools import WriteOnceDict
from fabengine.core import fab_core
from fabengine.cui.status import set_terminal_title
from fabengine.logserver import LoggingServer
from fabengine.package import (
    CompilerArgument,
    IncludePath,
    LibraryName,
    LinkerArgument,
    LinkerPath,
    Package,
    VariableDefinition,
    partition_specification,
    pkg_config,
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
        # If bits[1] doesn't exist, we're okay with that.
        pass

    try:  # Variable definitions
        carg_list = bits[2].split(",")
        for carg in carg_list:
            if not carg:
                continue
            variable_name, _, variable_value = carg.partition("=")
            cargs.append(VariableDefinition(variable_name, variable_value or None))
    except IndexError:
        # If bits[2] doesn't exist, we're okay with that.
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
        # If bits[3] doesn't exist, we're okay with that.
        pass

    try:  # Additional libraries
        larg_list = bits[4].split(",")
        for larg in larg_list:
            if not larg:
                continue
            largs.append(LibraryName(larg))
    except IndexError:
        # If bits[4] doesn't exist, we're okay with that.
        pass

    largs.append(LibraryName(bits[0].strip()))

    return Package(bits[0].strip(), (), cargs, largs)


def command_line(arguments: Sequence[str] | None = None) -> Namespace:
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
        "--bin-dir",
        "-b",
        type=Path,
        default="bin",
        help="Destination of executable binaries.",
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
        action="count",
        help="Provide running commentary on progress.",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="count",
        help="Get really chatty with running commentary.",
    )
    # Todo: At the moment, not all unit tests will run due to the feigner
    #       requiring MPI but only those tests which use it are launched with
    #       it. For the moment the logic will be inverted, but once
    #       everything's working right, testing should be the default.
    #
    parser.add_argument(
        "--test",
        dest="testing",
        action="store_true",
        help="Run tests associated with source.",
    )
    # parser.add_argument(
    #     "--no-test",
    #     dest="testing",
    #     action="store_false",
    #     help="Don't run tests associated with source.",
    # )
    parser.add_argument(
        "--logfile",
        "-l",
        type=Path,
        help="Path to comprehensive log file.",
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
    parser.add_argument(
        "--save-archive", type=Path, help="save the work directory to an archive file."
    )
    parser.add_argument(
        "--two-pass-compiles",
        action="store_true",
        help="Enable two pass compilations.",
    )
    options = parser.parse_args(arguments)

    if options.verbose is None:
        options.user_level = WARNING
    elif options.verbose == 1:
        options.user_level = INFO
    else:
        options.user_level = DEBUG

    if options.debug is None:
        options.system_level = WARNING
    elif options.debug == 1:
        options.system_level = INFO
    else:
        options.system_level = DEBUG

    if not options.bin_dir.is_absolute():
        options.bin_dir = options.work_dir / options.bin_dir

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


def pollute_configuration(configuration: WriteOnceDict) -> None:
    """
    Dump a lot of stuff into the configuration.

    .. todo:: This should be handled better, and at the build script level.
    """
    configuration["fc_ignore_modules"] = [
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
    ]
    configuration["field_instances"] = [
        {"real": "real32"},
        {"real": "real64"},
        {"integer": "int32"},
    ]
    configuration["build_tags"] = {
        "crusty": ["-std=gnu"],
        "um": ["-fdefault-real-8", "-fdefault-double-8"],
        "old-mpi": ["-fallow-argument-mismatch"],
        "gnu-intrinsics": ["-fall-intrinsics"],
        "nemo-nasty": ["-fdefault-real-8"],
        "nemo-crusty": ["-std=legacy"],
        "gnu-extensions": ["-std=gnu"],
    }
    configuration["tag_dirs"] = {
        "infrastructure/utilities/lfric_mpi_mod.f90": ["old-mpi"],
        "infrastructure/utilities/timer_mod_test.f90": ["gnu-intrinsics"],
        "casim/": ["um"],
        "jules/": ["um"],
        "physics_schemes/": ["um"],
        "physics_schemes_interface/legacy/": ["um"],
        "socrates/": ["um"],
        "ukca/": ["um"],
        "OCE/": ["nemo-nasty"],
        "OCE/nemogcm.f90": ["nemo-crusty"],
        "OCE/step.f90": ["gnu-extensions"],
        "OCE/stpctl.f90": ["nemo-crusty"],
        "OCE/timing.f90": ["nemo-crusty"],
        "OCE/DIA/diadct.f90": ["gnu-extensions"],
        "OCE/DIA/diaharm.f90": ["gnu-extensions"],
        "OCE/FLO/flodom.f90": ["gnu-extensions"],
        "OCE/ICB/icbdia.f90": ["gnu-extensions"],
        "OCE/ICB/icbdyn.f90": ["gnu-extensions"],
        "OCE/ICB/icbini.f90": ["gnu-extensions"],
        "OCE/ICB/icblbc.f90": ["nemo-crusty"],
        "OCE/ICB/icbstp.f90": ["gnu-extensions"],
        "OCE/ICB/icbthm.f90": ["gnu-extensions"],
        "OCE/ICB/icbutl.f90": ["gnu-extensions"],
        "OCE/ICB/icbtrj.f90": ["nemo-crusty"],
        "OCE/LBC/lib_mpp.f90": ["nemo-crusty"],
        "OCE/LBC/lbclnk.f90": ["nemo-crusty"],
        "OCE/OBS/mpp_map.f90": ["nemo-crusty"],
        "OCE/OBS/obs_mpp.f90": ["nemo-crusty"],
        "OCE/OBS/obs_oper.f90": ["gnu-extensions"],
        "OCE/OBS/obs_prep.f90": ["gnu-extensions"],
        "OCE/OBS/obs_readmdt.f90": ["gnu-extensions"],
        "OCE/SBC/fldread.f90": ["gnu-extensions"],
        "OCE/SBC/tide_mod.f90": ["gnu-extensions"],
        "OCE/TRD/trdvor.f90": ["gnu-extensions"],
        "ICE/": ["nemo-nasty"],
        "ioipsl/": ["nemo-nasty"],
    }
    configuration["inclusion_suffixes"] = [".h", ".inc", ".h90"]
    configuration["mock_tests"] = [
        "lfric_xios_diag_mod_test",
        "lfric_xios_read_mod_test",
        "lfric_xios_write_mod_test",
    ]
    configuration["use_open_mp"] = True
    configuration["internal_psyclone"] = True


def process_packages(
    build_script: BuildScript, library_map: list[Package], configuration: WriteOnceDict
) -> None:
    package_table = {package.name: package for package in library_map or []}
    for specification in build_script.packages():
        package_name, _, _ = partition_specification(specification)
        if package_name in package_table:
            configuration["packages"][package_name] = package_table[package_name]
        else:  # package_name not in package_table
            configuration["packages"][package_name] = pkg_config(specification)
    # Todo: Hardwired C++ runtime. Need a proper solution for language runtimes.
    #
    if "stdc++" not in configuration["packages"]:
        configuration["packages"]["stdc++"] = Package(
            "stdc++", (0, 0, 0), [], [LibraryName("stdc++")]
        )


def cli() -> None:
    """
    Command-line interface for Fab.
    """
    options = command_line()

    log_server = LoggingServer(
        options.logfile, options.user_level, options.system_level
    )

    with log_server:
        configuration = WriteOnceDict()
        configuration["monitor"] = options.monitor
        configuration["queue_strategy"] = options.queue_strategy
        configuration["testing"] = options.testing
        configuration["worker_threads"] = options.jobs
        configuration["archive_path"] = options.save_archive
        configuration["two_pass_compiles"] = options.two_pass_compiles

        configuration["paths"] = WriteOnceDict()
        configuration["paths"]["work_dir"] = options.work_dir
        configuration["paths"]["build_dir"] = (
            configuration["paths"]["work_dir"] / "build"
        )
        configuration["paths"]["module_dir"] = (
            configuration["paths"]["work_dir"] / "_fortran_modules"
        )
        configuration["paths"]["bin_dir"] = options.bin_dir
        configuration["paths"]["performance_file"] = options.timing_file
        configuration["packages"] = WriteOnceDict()

        # All directory paths have to exist
        for key, value in configuration["paths"].items():
            if key.endswith("_dir"):
                value.mkdir(exist_ok=True, parents=True)

        build_script = instantiate_build_script(options.fabfile)
        process_packages(build_script, options.map_library, configuration)
        configuration["repositories"] = build_script.repositories()
        configuration["forced_prerequisites"] = build_script.force_prerequisites()
        build_script.add_configuration(configuration)

        pollute_configuration(configuration)

        set_terminal_title(build_script.build_name)
        fab_core(configuration)
