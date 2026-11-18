from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from importlib.machinery import SourceFileLoader
from importlib.resources import files as import_files
from importlib.util import module_from_spec, spec_from_file_location
from inspect import getmembers, isclass
from logging import DEBUG, INFO, WARNING
from multiprocessing import set_start_method
from os import getenv
from pathlib import Path
from sys import argv

from yaml import safe_load

from fabengine.build_script import BuildScript
from fabengine.configuration_tools import WriteOnceDict
from fabengine.core import fab_core
from fabengine.cui.status import set_terminal_title
from fabengine.logserver import LoggingServer, make_logger
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


class CompilerType:
    """
    Return compiler from command line or environment variable (FC/CC/CXX)
    Raise an error if neither provided
    """

    def __init__(self, environment_variable: str):
        """
        :param environment_variable: Environment variable to read compiler from if
                                     command line not set. FC/CC/CXX
        """
        self._environment_variable = environment_variable

    def __call__(self, arg: str) -> str | None:
        """
        :param arg: Command line provided compiler argument
        """

        if arg:
            return arg

        compiler = getenv(self._environment_variable, None)
        if compiler:
            compiler = compiler.split("/")[-1]
        return compiler


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
        "--fc", default="", type=CompilerType("FC"), help="Fortran Compiler to be used"
    )
    parser.add_argument(
        "--cc", default="", type=CompilerType("CC"), help="C Compiler to be used"
    )
    parser.add_argument(
        "--extra_compilers",
        type=Path,
        help="Path to yaml file containing data for additional compilers",
    )
    parser.add_argument(
        "--extract-archive",
        type=Path,
        help="populate the work directory from an archive file.",
    )
    parser.add_argument(
        "--save-archive", type=Path, help="save the work directory to an archive file."
    )
    parser.add_argument(
        "--two-pass-compiles",
        action="store_true",
        help="Enable two pass compilations.",
    )
    parser.add_argument(
        "-s",
        "--dependencies-file",
        type=Path,
        help="Path to file containing repository source information.",
    )
    parser.add_argument("--metrics-csv", type=Path, help="Path to metrics CSV file.")
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
        "ifcore",  # For intel compilation
        "ifposix",
    ]

    configuration["field_instances"] = [
        {"real": "real32"},
        {"real": "real64"},
        {"integer": "int32"},
    ]

    configuration["inclusion_suffixes"] = [".h", ".inc", ".h90"]

    configuration["mock_tests"] = [
        "lfric_xios_diag_mod_test",
        "lfric_xios_read_mod_test",
        "lfric_xios_write_mod_test",
    ]


def process_packages(
    build_script: BuildScript, library_map: list[Package], configuration: WriteOnceDict
) -> None:
    configuration["packages"] = WriteOnceDict()
    package_table = {package.name: package for package in library_map or []}
    for specification in build_script.packages():
        package_name, _, _ = partition_specification(specification)
        if package_name in package_table:
            configuration["packages"][package_name] = package_table[package_name]
        else:  # package_name not in package_table
            configuration["packages"][package_name] = pkg_config(specification)
    # Todo: Hardwired C++ runtime. Need a proper solution for language runtimes.
    if "stdc++" not in configuration["packages"]:
        configuration["packages"]["stdc++"] = Package(
            "stdc++", (0, 0, 0), [], [LibraryName("stdc++")]
        )


def load_compiler_data(
    configuration: WriteOnceDict,
    extra_compilers: Path | None,
    fc: Path | str,
    cc: Path | str,
    two_pass_compiles: bool,
) -> None:
    """
    Load in compiler data from central and user sources.
    Select data based on compiler name
    TODO: Select the data based on compiler version as well as name. Use most specific
    available, eg. gfortran 12.2 over gfortran 12 over gfortran
    """

    with import_files("fabengine.data").joinpath("compilers.yaml").open("r") as f:
        compilers = safe_load(f)

    if extra_compilers and extra_compilers.exists():
        with open(extra_compilers, "r") as f:
            user_compilers = safe_load(f)

        # Combine known compiler data and user data. Prioritise user data
        compilers = compilers | user_compilers

    configuration["fc"] = fc
    if fc and fc in compilers:
        configuration["fortran_data"] = compilers[fc]

    configuration["cc"] = cc
    if cc and cc in compilers:
        configuration["c_data"] = compilers[cc]

    if two_pass_compiles and "syntax_only" in configuration["fortran_data"]:
        configuration["two_pass_compilation"] = True
    else:
        configuration["two_pass_compilation"] = False
        if two_pass_compiles:
            logger = make_logger("user")
            logger.warning(
                "Two Pass Compiles requested but not available for the current fortran "
                "compiler - switching to single pass compile instead."
            )


def validate_overrides(override_dict: dict) -> None:
    """
    Check that the entries to c/fortran overrides are of expected type and with only
    keys that the build system will understand.

    :param input_profile: Compiler profile to check
    """

    valid_keys = {
        "compile_flags": list,
        "openmp": bool,
    }

    for key, value in override_dict.items():
        if not isinstance(key, Path):
            raise TypeError(f"The key '{key}' is not of type Path.")
        if not isinstance(value, dict):
            raise TypeError(f"The value for key '{key}' is not a dict")
        for key2, value2 in value.items():
            if key2 not in valid_keys:
                raise AttributeError(f"The override key '{key2}' is unknown.")
            override_expected_type = valid_keys[key2]
            if not isinstance(value2, override_expected_type):
                raise TypeError(
                    f"The value '{value2}' of override key "
                    f"'{key2}' is not of expected type "
                    f"{override_expected_type}."
                )


def cli() -> None:
    """
    Command-line interface for Fab.
    """
    # Required to prevent multiprocessing failures >= 3.14
    set_start_method("fork")
    options = command_line()

    log_server = LoggingServer(
        options.logfile, options.user_level, options.system_level
    )

    with log_server:
        configuration = WriteOnceDict()
        build_script = instantiate_build_script(options.fabfile)
        process_packages(build_script, options.map_library, configuration)
        load_compiler_data(
            configuration,
            options.extra_compilers,
            options.fc,
            options.cc,
            options.two_pass_compiles,
        )
        configuration["paths"] = WriteOnceDict()
        configuration["paths"]["work_dir"] = options.work_dir
        configuration["paths"]["build_dir"] = (
            configuration["paths"]["work_dir"] / "build"
        )
        configuration["paths"]["module_dir"] = (
            configuration["paths"]["work_dir"] / "fortran_modules"
        )
        configuration["paths"]["bin_dir"] = options.bin_dir
        configuration["paths"]["performance_file"] = options.timing_file
        # All directory paths have to exist
        for key, value in configuration["paths"].items():
            if key.endswith("_dir"):
                value.mkdir(exist_ok=True, parents=True)

        validate_overrides(build_script.fortran_overrides())
        validate_overrides(build_script.c_overrides())

        configuration["repositories"] = build_script.repositories(
            options.dependencies_file
        )
        configuration["fpp_definitions"] = WriteOnceDict(build_script.fpp_definitions())
        configuration["forced_prerequisites"] = build_script.force_prerequisites()
        configuration["openmp"] = build_script.openmp()
        configuration["fortran_pp"] = build_script.fortran_pp()
        configuration["fortran_pp_flags"] = build_script.fortran_pp_flags()
        configuration["fortran_compile_flags_common"] = (
            build_script.fortran_compile_flags_common()
        )
        configuration["fortran_overrides"] = build_script.fortran_overrides()
        configuration["c_pp"] = build_script.c_pp()
        configuration["c_pp_flags"] = build_script.c_pp_flags()
        configuration["c_compile_flags_common"] = build_script.c_compile_flags_common()
        configuration["c_overrides"] = build_script.c_overrides()

        configuration["worker_threads"] = options.jobs
        configuration["monitor"] = options.monitor
        configuration["testing"] = options.testing
        configuration["queue_strategy"] = options.queue_strategy
        configuration["archive_path"] = options.save_archive
        configuration["extract_path"] = options.extract_archive
        configuration["two_pass_compiles"] = options.two_pass_compiles
        configuration["metrics_csv"] = options.metrics_csv
        configuration["internal_psyclone"] = True

        pollute_configuration(configuration)

        set_terminal_title(build_script.build_name)
        fab_core(configuration)
