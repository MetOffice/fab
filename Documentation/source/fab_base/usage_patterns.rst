Common Usage Pattern
====================

Creating a new site and platform
---------------------------------
To define a new site and platform, first create a directory with
Fab base class is. In this directory, create a file called
the name ``f"{site}_{platform}"`` in the directory in which the
``config.py``, which must define a class called ``Config``.

In general, it is recommended that any new config should inherit
from the default configuration (since this will typically provide
a good setup for various compilers). For example::

    from default.config import Config as DefaultConfig

    class Config(DefaultConfig):
        """
        A new site- and platform-specific setup file
        that sets the compiler default for this site to be
        intel-classic.
        """

        def __init__(self):
            super().__init__()
            tr = ToolRepository()
            tr.set_default_compiler_suite("intel-classic")

More methods can be overwritten to allow further customisation.


.. _better_help_messages:

Adding more command line options and better help messages
---------------------------------------------------------
As outlined in :ref:`define_command_line_options`, an
application can implement its own ``define_command_line_options``
method. An example which adds a new ``revision`` flag::

    class JulesBuild(FabBase):

        def define_command_line_options(self,
                                        parser: Optional[ArgumentParser] = None
                                        ) -> ArgumentParser:
            """
            :param parser: optional a pre-defined argument parser. If not, a
                new instance will be created.
            """
            parser = super().define_command_line_options(parser)
            parser.add_argument(
                "--revision", "-r", type=str, default="vn7.8",
                help="Sets the Jules revision to checkout.")
            return parser

Since the Python argument parser also allows specification of
a help message, this example can be extended as follows to provide
a better message::

    import argparse

    class JulesBuild(FabBase):

        def define_command_line_options(self,
                                        parser: Optional[ArgumentParser] = None
                                        ) -> ArgumentParser:
            """
            :param parser: optional a pre-defined argument parser. If not, a
                new instance will be created.
            """

            # Allow another derived class to provide its own parser (with its
            # own description message). If not, create a parser with a better
            # description:
            if not parser:
                parser = argparse.ArgumentParser(
                    description=("A Fab-based build system for Jules."),
                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

            super().define_command_line_options(parser)
            parser.add_argument(
                "--revision", "-r", type=str, default="vn7.8",
                help="Sets the Jules revision to checkout.")
            return parser

.. _handling_new_command_line_options:

Handling a new command line option
----------------------------------
As indicated in :ref:`define_command_line_options`, the method
``handle_command_line_options`` can be overwritten to handle
newly added command line options. Extending the previous
examples of a Jules build script, here is how the revision of
Jules is stored and then used::

    class JulesBuild(FabBase):

        def handle_command_line_options(self, parser):
            """
            Grab the requested (or default) Jules revision to use and
            store it in an attribute.
            """

            super().handle_command_line_options(parser)
            self._revision = self.args.revision

        def grab_files(self):
            """
            Extracts all the required source files from the repositories.
            """
            git_checkout(
                self.config,
                src="git@github.com:MetOffice/jules",
                revision=self._revision)

Strictly speaking, it is not necessary to store a command line option
that is already included in ``args`` as a separate attribute as shown
above - after all, the revision parameter could also be taken from
``self.args.revision`` instead. It is only done to make the code a little
bit easier to read, and make this part of the code independent of the
naming of the command line argument. If at some stage the command line
option for the Jules revision needs to be changed, the actual extract
step would not need to be changed.

.. _new_build_phase:

Adding a new phase into the build process
-----------------------------------------
A new phase can be inserted in the build process by overwriting
one of the existing steps, before or after which the new phase
should be executed. Here an example that adds PSyclone processing
for LFRic build script:

.. code-block:: python

    def preprocess_x90_step(self) -> None:
        """
        Invokes the Fab preprocess step for all X90 files.
        """
        # TODO: Fab does not support path-specific flags for X90 files.
        preprocess_x90(self.config,
                       common_flags=self.preprocess_flags_common)

    def psyclone_step(self) -> None:
    	"""
    	Call Fab's existing PSyclone step.
    	"""
    	psyclone(...)

    def analyse_step(self) -> None:
        '''
        The method overwrites the base class analyse_step.
        For LFRic, it first runs the preprocess_x90_step and then runs
        psyclone_step. Finally, it calls the original analyse step.
        '''
        self.preprocess_x90_step()
        self.psyclone_step()
        self.analyse_step()

A new step, i.e. one not already provided by Fab, is defined by using
Fab's ``step`` fixture. For example, to define a new ``remove_private_step``,
the following code is used:

.. code-block:: python

    from fab.steps import step

    @step
    def remove_private_step(self):
    	...

    def psyclone_step(self):
      '''
      Overwriting the psyclone_step method added above
      '''
      self.remove_private_step()
      super().psyclone_step()

.. _new_compilation_profiles:

Adding new compilation profiles
-------------------------------
This can be done in site-specific configuration files.
As shown in :ref:`use_default_configuration` it is recommended
to use a ``default`` configuration, which will allow for
consistency across sites. The following example shows
how a site can then add its own compilation profile:

.. code-block:: python

    def get_valid_profiles(self) -> List[str]:
        '''
        Determines the list of all allowed compiler profiles. Here we
        add one additional profile `memory-debug`. Note that the default
        setup will automatically create that profile mode for all tools.

        :returns List[str]: list of all supported compiler profiles.
        '''
        return super().get_valid_profiles() + ["memory-debug"]

This code will add a new ``memory-debug`` option, which can be selected
using the command line option ``--profile memory-debug``. Of course,
the site-specific config needs to then also set up this new mode.
For example:

.. code-block:: python

    def update_toolbox(self, build_config: BuildConfig) -> None:
        '''
        Define additional profiling mode 'memory-debug'.

        :param build_config: the Fab build configuration instance
        :type build_config: :py:class:`fab.BuildConfig`
        '''

        # The base class needs to be called first to create all
        # profile modes - this will include the newly defined in
        # the above get_valid_profiles call:
        super().update_toolbox(build_config)

        tr = ToolRepository()

        # Define the new compilation profile `memory-debug`
        gfortran = tr.get_tool(Category.FORTRAN_COMPILER, "gfortran")
        gfortran.add_flags(["-fsanitize=address"], "memory-debug")

        linker = tr.get_tool(Category.LINKER, "linker-gfortran")
        linker.add_post_lib_flags(["-static-libasan"], "memory-debug")

Running checkout and building independently
-------------------------------------------
On many platforms, only a few dedicated nodes might have internet access,
while the majority of compute nodes cannot access the internet at all.
In order to support these platforms, it is important that the checkout
of an application (e.g. using git) can be done without building, and
similarly that building can be executed without a checkout (meaning the
checkout must have ran before).

The FabBase class provides two command line options to support this:

1. ``--checkout-only``
    If this command line option is specified, Fab will exit (successfully)
    after ``grab_files_step``. If the user should be running additional
    tasks that require internet access, these must therefore be part of
    ``grab_files_step``. A user code might need to check for this flag
    (using ``fab_application.args.checkout_only``).

2. ``--skip-checkout``
    This command line parameter is intended to avoid running any checkouts
    (git, svn, ...). The Fab base class itself does not trigger any
    checkouts, and so this flag is not actually used internally. It is the
    responsibility of the application to implement this behaviour.
    Example code for this:

    .. code-block:: python

        for repo_info in repo_infos:
            if self.args.skip_checkout:
                logger.info(f"Skipping extraction of '{repo}' from "
                            f"'{repo_info.source}' ")
                continue

            logger.info(f"Extracting '{repo}' from '{repo_info.source}' "
                        f" to 'science/{repo}', "
                        f"revisions {repo_info.ref}")
            git_checkout(self.config,
                         repo_info.source,
                         dst_label=f'science/{repo}',
                         revision=repo_info.ref)

.. _dependencies_yaml_support:

Using a UK Met Office ``dependencies.yaml`` file
-------------------------------------------------
Many UK Met office repositories, for example LFRic and UM,
provide a ``dependencies.yaml`` file to specify dependencies
on other repositories. Here a (shortened) example from
LFRic:

.. code-block:: yaml

    casim:
        source: git@github.com:MetOffice/casim.git
        ref: 2026.07.1

    jules:
        source: git@github.com:MetOffice/jules.git
        ref: 2026.07.1

    lfric_core:
       source: git@github.com:MetOffice/lfric_core.git
       ref: 2026.07.1
    ...

Fab provides the class ``DependencyInfo`` to manage this kind
of yaml file. Example usage, taken from LFRic:

.. code-block:: python

    from fab.api import DependencyInfo
    ...

    def grab_files_step(self) -> None:

        yaml_file = Path("/some/path/to/dep.yaml")
        dep_info = DependencyInfo(yaml_file)

        # Loop over all dependency repositories:
        for repo in self.dependency_info.get_repo_names():
            repo_infos = self.dependency_info.get_repo_info(repo)

            # Each repo could have more than one branch listed,
            # so we might need to extract more than one branch:
            for repo_info in repo_infos:
                logger.info(f"Extracting '{repo}' from '{repo_info.source}' "
                            f" to 'science/{repo}', "
                            f"revisions {repo_info.ref}")
                try:
                    git_checkout(self.config,
                                 repo_info.source,
                                 dst_label=f'science/{repo}',
                                 revision=repo_info.ref)
                except RuntimeError as error:
                    logger.error(f"Cannot checkout '{repo}' from "
                                 f"'{repo_info.source}' revision "
                                 f"'{repo_info.ref}': {error}. ")
                    sys.exit(-1)
