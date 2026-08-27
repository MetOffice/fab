#! /usr/bin/env python3


'''
This module contains the default Fab configuration class.
'''

import argparse

from fab.build_config import BuildConfig
from fab.tools.profile_flags import ProfileFlags


class Config:
    '''
    This class is the default Configuration object for Fab builds.
    It provides several callbacks which will be called from the build
    scripts to allow site-specific customisations.
    '''

    def __init__(self):
        self._args = None

    def __str__(self) -> str:
        return "SiteSpecificDefault"

    @property
    def args(self) -> argparse.Namespace:
        '''
        :returns argparse.Namespace: the command line options specified
            by the user.
        '''
        return self._args

    def get_valid_profiles(self) -> list[str]:
        '''
        Determines the list of all allowed compiler profiles. The first
        entry in this list is the default profile to be used. This method
        can be overwritten by site configs to add or modify the supported
        profiles.

        :returns list[str]: list of all supported compiler profiles.
        '''
        return ["default-profile", "full-debug", "fast-debug", "production"]

    def update_toolbox(self, build_config: BuildConfig) -> None:
        '''
        Set the default compiler flags for the various compiler
        that are supported.

        :param build_config: the Fab build configuration instance
        :type build_config: :py:class:`fab.BuildConfig`
        '''
        # First create the default compiler profiles.
        # Define a base profile, which contains the common
        # compilation flags. This 'base' is not accessible to
        # the user, so it's not part of the profile list.
        ProfileFlags.define_profile("base")
        for profile in self.get_valid_profiles():
            ProfileFlags.define_profile(profile, inherit_from="base")

    def define_command_line_options(self,
                                    parser: argparse.ArgumentParser) -> None:
        '''
        Callback in which additional, site-specific options can be added,
        and/or the the defaults for the parser can be changed.
        '''
        # Example: change the MPI default (enabling this would break tests):
        # parser.set_defaults(mpi=False)

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
