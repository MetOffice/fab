#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Class which can be subclassed to create fab build targets.
"""

from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace


class FabTargetBase(ABC):
    """Abstract base class for creating fab build targets."""

    @property
    @abstractmethod
    def project_name(self):
        """Require subclasses to set a project name.

        Defining project_name as an abstract property requires every
        subclass to set a valid name.
        """

    @staticmethod
    def add_arguments(parser: ArgumentParser) -> None:
        """Extend an existing argument parser.

        Add arguments to an ArgumentParser instance provided by the
        fab command.  This allows build target classes to make their
        own options visible in the argument parser used by the
        command.

        :param ArgumentParser parser: an existing command line argument parser.
        """

    @staticmethod
    def check_arguments(parser: ArgumentParser, args: Namespace) -> None:
        """Validate the command line arguments.

        Check the command line arguments for correctness, allowing the
        ArgumentParser.error method to used to raise usage problems.

        :param ArgumentParser parser: an existing command line argument parser.
        :param Namespace args: parsed arguments

        """

    @abstractmethod
    def run(self, args: Namespace) -> None:
        """Run arbitrary build actions.

        Entry point used by the fab command to run the actions
        required to build a particular target.  This must be
        implemented by the target subclass.

        :param Namespace args: the parsed command line arguments.
        """
