#! /usr/bin/env python3


'''
This module contains the default Baf configuration class.
'''

import argparse
from typing import cast, Dict, List

from fab.build_config import AddFlags, BuildConfig
from fab.tools import Category, Compiler, ToolRepository

from fab.fab_base.site_specific.default.setup_cray import setup_cray
from fab.fab_base.site_specific.default.setup_gnu import setup_gnu
from fab.fab_base.site_specific.default.setup_intel_classic import (
    setup_intel_classic)
from fab.fab_base.site_specific.default.setup_intel_llvm import (
    setup_intel_llvm)
from fab.fab_base.site_specific.default.setup_nvidia import setup_nvidia


class Config:
    '''
    This class is the default Configuration object for Baf builds.
    It provides several callbacks which will be called from the build
    scripts to allow site-specific customisations.
    '''

    def __init__(self) -> None:
        self._args: argparse.Namespace

        # Stores for each compiler suite a mapping of profiles to the list of
        # path-specific flags to use.
        # _path_flags[suite][profile]
        self._path_flags: Dict[str, Dict[str, List[AddFlags]]] = {}

    @property
    def args(self) -> argparse.Namespace:
        '''
        :returns: the command line options specified by the user.
        '''
        return self._args

    def get_valid_profiles(self) -> List[str]:
        '''
        Determines the list of all allowed compiler profiles. The first
        entry in this list is the default profile to be used. This method
        can be overwritten by site configs to add or modify the supported
        profiles.

        :returns: list of all supported compiler profiles.
        '''
        return ["full-debug", "fast-debug", "production", "unit-tests"]

    def handle_command_line_options(self, args: argparse.Namespace) -> None:
        '''
        Additional callback function executed once all command line
        options have been added. This is for example used to add
        Vernier profiling flags, which are site-specific.

        :param argparse.Namespace args: the command line options added in
            the site configs
        '''
        # Keep a copy of the args, so they can be used when
        # initialising compilers
        self._args = args

    def update_toolbox(self, build_config: BuildConfig) -> None:
        '''
        Set the default compiler flags for the various compiler
        that are supported.

        :param build_config: the Fab build configuration instance
        '''
        # First create the default compiler profiles for all available
        # compilers. While we have a tool box with exactly one compiler
        # in it, compiler wrappers will require more than one compiler
        # to be initialised - so we just initialise all of them (including
        # the linker):
        tr = ToolRepository()
        for compiler in (tr[Category.C_COMPILER] +
                         tr[Category.FORTRAN_COMPILER] +
                         tr[Category.LINKER]):
            # Define a base profile, which contains the common
            # compilation flags. This 'base' is not accessible to
            # the user, so it's not part of the profile list. Also,
            # make it inherit from the default profile '', so that
            # a user does not have to specify the 'base' profile.
            # Note that we set this even if a compiler is not available.
            # This is required in case that compilers are not in PATH,
            # so e.g. mpif90-ifort works, but ifort cannot be found.
            # We still need to be able to set and query flags for ifort.
            compiler.define_profile("base", inherit_from="")
            for profile in self.get_valid_profiles():
                compiler.define_profile(profile, inherit_from="base")

        self.setup_intel_classic(build_config)
        self.setup_intel_llvm(build_config)
        self.setup_gnu(build_config)
        self.setup_nvidia(build_config)
        self.setup_cray(build_config)

    def get_path_flags(self, build_config: BuildConfig) -> List[AddFlags]:
        '''
        Returns the path-specific flags to be used.
        TODO #313: Ideally we have only one kind of flag, but as a quick
        work around we provide this method.
        '''
        compiler = build_config.tool_box[Category.FORTRAN_COMPILER]
        compiler = cast(Compiler, compiler)
        return self._path_flags[compiler.suite].get(build_config.profile, [])

    def setup_cray(self, build_config: BuildConfig) -> None:
        '''
        This method sets up the Cray compiler and linker flags.
        For now call an external function, since it is expected that
        this configuration can be very lengthy (once we support
        compiler modes).

        :param build_config: the Fab build configuration instance
        '''
        self._path_flags["cray"] = setup_cray(build_config, self.args)

    def setup_gnu(self, build_config: BuildConfig) -> None:
        '''
        This method sets up the Gnu compiler and linker flags.
        For now call an external function, since it is expected that
        this configuration can be very lengthy (once we support
        compiler modes).

        :param build_config: the Fab build configuration instance
        '''
        self._path_flags["gnu"] = setup_gnu(build_config, self.args)

    def setup_intel_classic(self, build_config: BuildConfig) -> None:
        '''
        This method sets up the Intel classic compiler and linker flags.
        For now call an external function, since it is expected that
        this configuration can be very lengthy (once we support
        compiler modes).

        :param build_config: the Fab build configuration instance
        '''
        self._path_flags["intel_classic"] = setup_intel_classic(build_config,
                                                                self.args)

    def setup_intel_llvm(self, build_config: BuildConfig) -> None:
        '''
        This method sets up the Intel LLVM compiler and linker flags.
        For now call an external function, since it is expected that
        this configuration can be very lengthy (once we support
        compiler modes).

        :param build_config: the Fab build configuration instance
        '''
        self._path_flags["intel-llvm"] = setup_intel_llvm(build_config,
                                                          self.args)

    def setup_nvidia(self, build_config: BuildConfig) -> None:
        '''
        This method sets up the Nvidia compiler and linker flags.
        For now call an external function, since it is expected that
        this configuration can be very lengthy (once we support
        compiler modes).

        :param build_config: the Fab build configuration instance
        '''
        self._path_flags["nvidia"] = setup_nvidia(build_config, self.args)
