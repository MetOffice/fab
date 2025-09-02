#!/usr/bin/env python3
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''
This is an OO basic interface to FAB. It allows typical applications to
only modify very few settings to have a working FAB build script.
'''

import argparse
from importlib import import_module
import inspect
import logging
import os
from pathlib import Path
import sys
from typing import List, Optional, Union, Iterable

from fab.build_config import AddFlags, BuildConfig
from fab.steps.analyse import analyse
from fab.steps.archive_objects import archive_objects
from fab.steps.c_pragma_injector import c_pragma_injector
from fab.steps.compile_c import compile_c
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files, Exclude, Include
from fab.steps.grab.folder import grab_folder
from fab.steps.link import link_exe, link_shared_object
from fab.steps.preprocess import preprocess_c, preprocess_fortran
from fab.tools import Category, ToolBox, ToolRepository


class FabBase:
    '''
    This is a convenience base class for writing Fab scripts. It provides
    an extensive set of command line options that can be used to influence
    the build process, and can be extended by applications. It has already
    support for compilation modes, and allows site-specific configuration
    scripts to be written that can modify the initialisation and build
    process.

    :param name: the name to be used for the workspace. Note that
        the name of the compiler will be added to it.
    :param link_target: what target should be created. Must be one of
        "executable" (default), "static-library", or "shared-library"
    '''
    # pylint: disable=too-many-instance-attributes
    def __init__(self,
                 name: str,
                 link_target: str = "executable") -> None:
        self.set_link_target(link_target)
        self._logger = logging.getLogger(__name__)
        self._site = None
        self._platform = None
        # Save the name to use as library name (if required)
        self._name = name
        self._target = ""
        # Set the given name as root symbol, it can be set explicitly
        # using set_root_symbol()
        self._root_symbol: List[str] = [name]

        # The preprocessor flags to be used. One stores the common flags
        # (without path-specific component), the other the path-specific
        # flags (which are still handled separately in Fab)
        self._preprocessor_flags_common: List[str] = []
        self._preprocessor_flags_path: List[AddFlags] = []

        # The compiler and linker flags from the command line
        self._fortran_compiler_flags_commandline: List[str] = []
        self._c_compiler_flags_commandline: List[str] = []
        self._linker_flags_commandline: List[str] = []

        # We have to determine the site-specific setup first, so that e.g.
        # new compilers can be added before command line options are handled
        # (which might request this new compiler). So first parse the command
        # line for --site and --platform only:
        self.define_site_platform_target()

        # Now that site, platform and target are defined, import any
        # site-specific settings
        self.site_specific_setup()

        # Define the tool box, which might be started to be filled
        # when handling command line options:
        self._tool_box = ToolBox()
        parser = self.define_command_line_options()
        self.handle_command_line_options(parser)
        # Now allow further site-customisations depending on
        # the command line arguments
        if self._site_config:
            self._site_config.handle_command_line_options(self.args)

        label = self.define_project_name(name=name)
        if self.args.fab_workspace:
            fab_workspace = Path(self.args.fab_workspace)
        else:
            # If not specified, set it to None, in which case the
            # Fab default will be used.
            fab_workspace = None
        self._config = BuildConfig(tool_box=self._tool_box,
                                   project_label=label,
                                   verbose=True,
                                   n_procs=self.args.nprocs,
                                   mpi=self.args.mpi,
                                   openmp=self.args.openmp,
                                   profile=self.args.profile,
                                   fab_workspace=fab_workspace,
                                   )

        if self._site_config:
            self._site_config.update_toolbox(self._config)

    def set_link_target(self, link_target: str) -> None:
        '''
        Sets the link target.

        :param link_target: what target should be created. Must be one of
            "executable"s, "static-library", or "shared-library".

        :raises ValueError: if the link_target is invalid
        '''
        link_target = link_target.lower()
        valid_targets = ["executable", "static-library", "shared-library"]
        if link_target not in valid_targets:
            raise ValueError(f"Invalid parameter '{link_target}', must be "
                             f"one of '{', '.join(valid_targets)}'.")
        self._link_target = link_target

    def define_project_name(self, name: str) -> str:
        '''
        This method defines the project name, i.e. the directory name to
        use in the Fab workspace. It defaults to `name-profile-compiler`.

        :param name: the base name of the project as specified by the caller.

        :returns: the project name
        '''
        label = f"{name}-{self.args.profile}-$compiler"
        return label

    def set_root_symbol(self, root_symbol: Union[List[str], str]) -> None:
        '''Defines the root symbol. It defaults to the name given in
        the constructor.

        :param name: the root symbol to use when creating a binary
            (unused otherwise).
        '''
        if isinstance(root_symbol, str):
            self._root_symbol = [root_symbol]
        else:
            self._root_symbol = root_symbol

    @property
    def root_symbol(self) -> List[str]:
        '''
        :returns: the list of root symbols.
        '''
        return self._root_symbol

    @property
    def site(self) -> Optional[str]:

        '''
        :returns: the site, or None if no site is specified.
        '''
        return self._site

    @property
    def logger(self) -> logging.Logger:
        '''
        :returns: the logging instance to use.
        '''
        return self._logger

    @property
    def platform(self) -> Optional[str]:
        '''
        :returns: the platform, or None if not specified.
        '''
        return self._platform

    @property
    def target(self) -> str:
        '''
        :returns: the target (="site-platform"), or "default"
            if nothing was specified.
        '''
        return self._target

    @property
    def config(self) -> BuildConfig:
        '''
        :returns: the FAB BuildConfig instance.
        :rtype: :py:class:`fab.BuildConfig`
        '''
        return self._config

    @property
    def args(self) -> argparse.Namespace:
        '''
        :returns: the arg parse objects containing the user's
            command line information.
        '''
        return self._args

    @property
    def project_workspace(self) -> Path:
        '''
        :returns: the Fab workspace for this build.
        '''
        return self._config.project_workspace

    @property
    def preprocess_flags_common(self) -> List[str]:
        """
        :returns: the list of all common preprocessor flags.
        """
        return self._preprocessor_flags_common

    @property
    def preprocess_flags_path(self) -> List[AddFlags]:
        """
        :returns: the list of all path-specific flags.
        """
        return self._preprocessor_flags_path

    @property
    def fortran_compiler_flags_commandline(self) -> List[str]:
        """
        :returns: the list of flags specified through --fflags.
        """
        return self._fortran_compiler_flags_commandline

    @property
    def c_compiler_flags_commandline(self) -> List[str]:
        """
        :returns: the list of flags specified through --cflags.
        """
        return self._c_compiler_flags_commandline

    @property
    def linker_flags_commandline(self) -> List[str]:
        """
        :returns: the list of flags specified through --ldflags.
        """
        return self._linker_flags_commandline

    def setup_site_specific_location(self) -> None:
        '''
        This method adds the required directories for site-specific
        configurations to the Python search path. This implementation will
        search the call tree to find the first call that's not from Fab,
        i.e. the user script. It then adds ``site_specific`` and
        ``site_specific/default`` to the directory in which the user script
        is located. An application can overwrite this method to change this
        behaviour and point at site-specific directories elsewhere.
        '''
        my_base_dir = Path(__file__).parent
        for caller in inspect.stack():
            dir_caller = Path(caller[1]).parent
            if not my_base_dir.samefile(dir_caller):
                # This is required in case that the script is not
                # called from the script directory, but site_specific
                # is in the directory of the script.
                sys.path.insert(0, str(dir_caller))
                break
        else:
            # All callers are in this directory? Add a warning, and
            # setup `dir_caller` to . (which is already added to the
            # path, so it doesn't need to be added), so site-specific
            # will be added below.
            dir_caller = Path(".")
            self.logger.warning("Could not find caller directory, "
                                "defaulting to '.'.")

        # We need to add the 'site_specific' directory to the path, so
        # each config can import from 'default' (instead of having to
        # use 'site_specific.default', which would hard-code the name
        # `site_specific` in more scripts).
        sys.path.insert(0, str(dir_caller / "site_specific"))

    def define_site_platform_target(self) -> None:
        '''
        This method defines the attributes site, platform (and
        target=site-platform) based on the command line option --site
        and --platform (using $SITE and $PLATFORM as a default). If
        site or platform is missing and the corresponding environment
        variable is not set, 'default' will be used.
        '''

        # Use `argparser.parse_known_args` to just handle --site and
        # --platform. We also suppress help (all of which will be handled
        # later, including proper help messages)
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--site", "-s", type=str, default="$SITE")
        parser.add_argument("--platform", "-p", type=str, default="$PLATFORM")

        args = parser.parse_known_args()[0]   # Ignore element [1]=unknown args
        if args.site == "$SITE":
            self._site = os.environ.get("SITE", "default")
        else:
            self._site = args.site

        if args.platform == "$PLATFORM":
            self._platform = os.environ.get("PLATFORM", "default")
        else:
            self._platform = args.platform

        # Define target attribute for site&platform-specific files
        # If none are specified, just use a single default (instead of
        # default-default)
        if self._platform == "default" and self._site == "default":
            self._target = "default"
        else:
            self._target = f"{self._site}_{self._platform}"

    def site_specific_setup(self) -> None:
        '''
        Imports a site-specific config file. The location is based
        on the attribute ``target`` (which is set to be ``{site}_{platform}"
        based on the command line options, and the path is specified
        in ``setup_site_specific_location``).
        '''
        self.setup_site_specific_location()
        try:
            config_name = f"site_specific.{self.target}.config"
            config_module = import_module(config_name)
        except ModuleNotFoundError as err:
            # We log a warning, but proceed, since there is no need to
            # have a site-specific file.
            self._logger.warning(f"Cannot find site-specific module "
                                 f"'{config_name}': {err}.")
            self._site_config = None
            return
        self.logger.info(f"fab_base: Imported '{config_module.__file__}'.")
        # The constructor handles everything.
        self._site_config = config_module.Config()

    def define_command_line_options(
            self,
            parser: Optional[argparse.ArgumentParser] = None
            ) -> argparse.ArgumentParser:
        '''
        Defines command line options. Can be overwritten by a derived
        class which can provide its own instance (to easily allow for a
        different description).

        :param parser: optional a pre-defined argument parser. If not, a
            new instance will be created.
        '''

        if not parser:
            # The formatter class makes sure to print default settings
            parser = argparse.ArgumentParser(
                description=("A Fab-based build system. Note that if --suite "
                             "is specified, this will change the default for "
                             "compiler and linker"),
                formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        parser.add_argument(
            '--suite', '-v', type=str, default=None,
            help="Sets the default suite for compiler and linker")
        parser.add_argument(
            '--available-compilers', default=False, action="store_true",
            help="Displays the list of available compilers and linkers")
        parser.add_argument(
            '--fc', '-fc', type=str, default="$FC",
            help="Name of the Fortran compiler to use")
        parser.add_argument(
            '--cc', '-cc', type=str, default="$CC",
            help="Name of the C compiler to use")
        parser.add_argument(
            '--ld', '-ld', type=str, default="$LD",
            help="Name of the linker to use")
        parser.add_argument(
            '--fflags', '-fflags', type=str, default=None,
            help="Flags to be used by the Fortran compiler. The command line "
                 "flags are appended after compiler flags defined in a "
                 "site-specific setup and after getting flags from the "
                 "environment variable $FFLAGS. Therefore, this can be used "
                 "to overwrite certain flags.")
        parser.add_argument(
            '--cflags', '-cflags', type=str, default=None,
            help="Flags to be used by the C compiler. The command line "
                 "flags are appended after compiler flags defined in a "
                 "site-specific setup and after getting flags from the "
                 "environment variable $CFLAGS. Therefore, this can be used "
                 "to overwrite certain flags.")
        parser.add_argument(
            '--ldflags', '-ldflags', type=str, default=None,
            help="Flags to be used by the linker. The command line "
                 "flags are appended after linker flags defined in a "
                 "site-specific setup and after getting flags from the "
                 "environment variable $LDFLAGS. Therefore, this can be used "
                 "to overwrite certain flags.")

        parser.add_argument(
            '--nprocs', '-n', type=int, default=1,
            help="Number of processes (default is 1)")
        parser.add_argument(
            '--mpi', '-mpi', default=True, action="store_true",
            help="Enable MPI")
        parser.add_argument(
            '--no-mpi', '-no-mpi', action="store_false",
            dest="mpi", help="Disable MPI")
        parser.add_argument(
            '--openmp', '-openmp', default=True, action="store_true",
            help="Enable OpenMP")
        parser.add_argument(
            '--no-openmp', '-no-openmp', action="store_false",
            dest="openmp", help="Disable OpenMP")
        parser.add_argument(
            '--openacc', '-openacc', default=True, action="store_true",
            help="Enable OpenACC")
        parser.add_argument(
            '--host', '-host', default="cpu", type=str,
            help="Determine the OpenACC or OpenMP: either 'cpu' or 'gpu'.")

        parser.add_argument("--site", "-s", type=str,
                            default="$SITE or 'default'",
                            help="Name of the site to use.")
        parser.add_argument("--platform", "-p", type=str,
                            default="$PLATFORM or 'default'",
                            help="Name of the platform of the site to use.")
        parser.add_argument("--fab-workspace", type=str,
                            default=None,
                            help="Fab workspace, in which the build "
                                 "directory will be created.")
        if self._site_config:
            valid_profiles = self._site_config.get_valid_profiles()
            parser.add_argument(
                '--profile', '-pro', type=str, default=valid_profiles[0],
                help=(f"Sets the compiler profile, choose from "
                      f"'{valid_profiles}'."))
        return parser

    def handle_command_line_options(self,
                                    parser: argparse.ArgumentParser) -> None:
        '''
        Analyse the actual command line options using the specified parser.
        The base implementation will handle the `--suite` parameter, and
        compiler/linker parameters (including the usage of environment
        variables). Needs to be overwritten to handle additional options
        specified by a derived script.

        :param argparse.ArgumentParser parser: the argument parser.
        '''
        # pylint: disable=too-many-branches
        self._args = parser.parse_args(sys.argv[1:])
        if self.args.host.lower() not in ["", "cpu", "gpu"]:
            raise RuntimeError(f"Invalid host directive "
                               f"'{self.args.host}'. Must be "
                               f"'cpu' or 'gpu'.")

        tr = ToolRepository()
        if self.args.available_compilers:
            all_available = []
            # We don't print the values immediately, since `is_available` runs
            # tests with debugging enabled, which adds a lot of debug output.
            # Instead write the combined list at the end and then exit.
            for compiler in tr[Category.C_COMPILER]:
                if compiler.is_available:
                    all_available.append(compiler)
            for compiler in tr[Category.FORTRAN_COMPILER]:
                if compiler.is_available:
                    all_available.append(compiler)
            for linker in tr[Category.LINKER]:
                if linker.is_available:
                    all_available.append(linker)
            print("\n----- Available compiler and linkers -----")
            for tool in all_available:
                print(tool)
            sys.exit()

        if not self._site_config:
            # If there is no site config, use the default (empty) profile
            self.args.profile = ""
        else:
            # Otherwise make sure the selected profile is supported:
            # If no --profile is supported, it will default to the first
            # profile in the site config file.
            if (self.args.profile and self.args.profile
                    not in self._site_config.get_valid_profiles()):
                raise RuntimeError(f"Invalid profile '{self.args.profile}")

        if self.args.suite:
            tr.set_default_compiler_suite(self.args.suite)

            self.logger.info(f"Setting suite to '{self.args.suite}'.")
            # suite will overwrite use of env variables, so change the
            # value of these arguments to be none so they will be ignored
            if self.args.fc == "$FC":
                self.args.fc = None
            if self.args.cc == "$CC":
                self.args.cc = None
            if self.args.ld == "$LD":
                self.args.ld = None
        else:
            # If no suite is specified, if required set the defaults
            # for compilers based on the environment variables.
            if self.args.fc == "$FC":
                self.args.fc = os.environ.get("FC")
            if self.args.cc == "$CC":
                self.args.cc = os.environ.get("CC")
            if self.args.ld == "$LD":
                self.args.ld = os.environ.get("LD")

        # If no suite was specified, and a special tool was requested,
        # add it to the tool box:
        if self.args.cc:
            cc = tr.get_tool(Category.C_COMPILER, self.args.cc)
            self._tool_box.add_tool(cc)
        if self.args.fc:
            fc = tr.get_tool(Category.FORTRAN_COMPILER, self.args.fc)
            self._tool_box.add_tool(fc)
        if self.args.ld:
            ld = tr.get_tool(Category.LINKER, self.args.ld)
            self._tool_box.add_tool(ld)

        # If the user specified compiler flags in the
        # environment variables CFLAGS, FFLAGS, LDFLAGS, add them to the
        # list of flags to be used by the corresponding tools.
        self._fortran_compiler_flags_commandline = \
            os.environ.get("FFLAGS", "").split()
        self._c_compiler_flags_commandline = \
            os.environ.get("CFLAGS", "").split()
        self._linker_flags_commandline = \
            os.environ.get("LDFLAGS", "").split()

        if self.args.fflags:
            # If the user specified Fortran compiler flags, add them
            # to the list of flags to be used by the Fortran compiler.
            self._fortran_compiler_flags_commandline += \
                self.args.fflags.split()
        if self.args.cflags:
            # If the user specified C compiler flags, add them
            # to the list of flags to be used by the C compiler.
            self._c_compiler_flags_commandline += \
                self.args.cflags.split()
        if self.args.ldflags:
            # If the user specified linker flags, add them
            # to the list of flags to be used by the linker.
            self._linker_flags_commandline += \
                self.args.ldflags.split()

    def define_preprocessor_flags_step(self) -> None:
        '''
        Top level function that sets preprocessor flags. The base
        implementation does nothing, should be overwritten.
        '''

    def get_linker_flags(self) -> List[str]:
        '''
        Base class for setting linker flags. This base implementation
        for now just returns an empty list.

        :returns: list of flags for the linker.
        '''
        return []

    def add_preprocessor_flags(
            self,
            list_of_flags: Union[AddFlags, str, List[AddFlags], List[str]]
            ) -> None:
        """
        This function appends a preprocessor flags to the internal list of
        all preprocessor flags, which will be passed to Fab's various
        preprocessing steps (for C, Fortran, and X90).

        Each flag can be either a str, or a path-specific instance of
        Fab's AddFlags object. For the convenience of the user, this function
        also accepts a single flag or a list of flags.

        No checking will be done if a flag is already in the list of flags.

        :param list_of_flags: the preprocessor flag(s) to add. This can be
            either a ``str`` or an ``AddFlags``, and in each case either a
            single item or a list.
        """

        # This convoluted test makes mypy happy
        if isinstance(list_of_flags, AddFlags):
            list_of_flags = [list_of_flags]
        elif isinstance(list_of_flags, str):
            list_of_flags = [list_of_flags]

        # While Fab still distinguishes between path-specific and common
        # flags, we have to sort these flags here:
        for flag in list_of_flags:
            if isinstance(flag, AddFlags):
                self._preprocessor_flags_path.append(flag)
            else:
                self._preprocessor_flags_common.append(flag)

    def grab_files_step(self) -> None:
        '''
        This should typically be overwritten by an application to
        get files e.g. from a repository.
        '''
        if type(self).__name__ == "FabBase":
            # Do a simple build based on files in "." if FabBase is
            # started by itself (and not inherited):
            grab_folder(self.config, src=".")

    def find_source_files_step(
            self,
            path_filters: Optional[Iterable[Union[Exclude, Include]]] = None
            ) -> None:
        """
        This function calls Fab's find_source_files, to identify and add
        all source files to Fab's artefact store.

        :param path_filters: optional list of path filters to be passed to
            Fab find_source_files, default is None.
        """
        find_source_files(self.config, path_filters=path_filters)

    def preprocess_c_step(self) -> None:
        """
        Calls Fab's preprocessing of all C files. It passes the
        common and path-specific flags set using add_preprocessor_flags.
        """
        preprocess_c(self.config,
                     common_flags=self.preprocess_flags_common,
                     path_flags=self.preprocess_flags_path)

    def preprocess_fortran_step(self) -> None:
        """
        Calls Fab's preprocessing of all fortran files. It passes the
        common and path-specific flags set using add_preprocessor_flags.
        """
        preprocess_fortran(self.config,
                           common_flags=self.preprocess_flags_common,
                           path_flags=self.preprocess_flags_path)

    def analyse_step(self, find_programs: bool = False) -> None:
        """
        Calls Fab's analyse. It passes the config and root symbol for
        Fab to analyze the source code dependencies.

        :find_programs: if set and an executable is created (see link_target),
            the flag will be set in Fab's analyse step, which means it will
            identify all main programs automatically.
        """
        if self._link_target == "executable":
            if find_programs or type(self).__name__ == "FabBase":
                # Automatically find the main programs:
                analyse(self.config, find_programs=True)
            else:
                analyse(self.config, root_symbol=self.root_symbol)
        else:
            analyse(self.config, root_symbol=None)

    def compile_c_step(
            self,
            common_flags: Optional[List[str]] = None,
            path_flags: Optional[List[AddFlags]] = None
            ) -> None:
        """
        Calls Fab's compile_c. It passes the config for Fab to compile
        all C files. Optionally, common flags, path-specific flags and
        alternative source can also be passed to Fab for compilation.
        """
        site_path_flags: List[AddFlags] = []
        if self._site_config:
            site_path_flags = self._site_config.get_path_flags(self._config)
        if not common_flags:
            common_flags = []
            assert isinstance(common_flags, list)
        if not path_flags:
            path_flags = []

        compile_c(self.config,
                  common_flags=(common_flags +
                                self.c_compiler_flags_commandline),
                  path_flags=path_flags + site_path_flags)

    def compile_fortran_step(
            self,
            common_flags: Optional[List[str]] = None,
            path_flags: Optional[List[AddFlags]] = None
            ) -> None:
        """
        Calls Fab's compile_fortran. It passes the config for Fab to
        compile all Fortran files. Optionally, common flags, path-specific
        flags and alternative source can also be passed to Fab for
        compilation.

        :param path_flags: optional list of path-specific flags to be passed
            to Fab compile_fortran, default is None.
        """
        site_path_flags: List[AddFlags] = []
        if self._site_config:
            site_path_flags = self._site_config.get_path_flags(self._config)
        if not common_flags:
            common_flags = []
        if not path_flags:
            path_flags = []
        compile_fortran(self.config,
                        common_flags=(common_flags +
                                      self.fortran_compiler_flags_commandline),
                        path_flags=path_flags + site_path_flags)

    def link_step(self) -> None:
        """
        Calls Fab's archive_objects for creating static libraries, or
        link_shared_object for creating shared libraries, or link_exe for
        creating executable binaries. The outputs will be placed in the Fab
        workspace, either using the name or root_symbol passed to the Fab
        build config.
        """
        if self._link_target == "static-library":
            out_path = self.config.project_workspace / f"lib{self._name}.a"
            archive_objects(self.config,
                            output_fpath=str(out_path))
        elif self._link_target == "shared-library":
            out_path = self.config.project_workspace / f"lib{self._name}.so"
            link_shared_object(self.config,
                               output_fpath=str(out_path),
                               flags=self.linker_flags_commandline)
        else:
            # Binary:
            link_exe(self.config, libs=self.get_linker_flags(),
                     flags=self.linker_flags_commandline)

    def build(self) -> None:
        """
        This function defines the build process for Fab. Generally, a build
        process involves grabbing and finding Fortran and C source files for
        proprocessing, dependency analysis, compilation and linking.
        """
        # We need to use "with" to trigger the entrance/exit functionality,
        # but otherwise the config object is used from this object, so no
        # need to use it anywhere.
        with self._config as _:
            self.grab_files_step()
            self.find_source_files_step()
            # This is a Fab function, which the user won't need to be
            # able to overwrite.
            c_pragma_injector(self.config)
            self.define_preprocessor_flags_step()
            self.preprocess_c_step()
            self.preprocess_fortran_step()
            self.analyse_step()
            self.compile_c_step()
            self.compile_fortran_step()
            # Disable archiving due to
            # https://github.com/MetOffice/fab/issues/310
            self.link_step()


# ==========================================================================
if __name__ == "__main__":
    # This tests the FabBase class using the command line.
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    fab_base = FabBase(name="command-line-test")
    fab_base.build()
