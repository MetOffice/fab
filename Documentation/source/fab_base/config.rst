.. _site_specific_configuration_files:

Site-specific Configuration Files
=================================

This chapter describes the design of the site-specific
configuration files. It starts with the concept, and then
includes some examples.

Concepts for site-specific setup
--------------------------------
Fab's base class supports site-specific setup, and it is is based on
using a site name and a platform name.
For example, The UK Met Office traditionally
uses ``meto`` as site name, and then a different platform name, e.g.
``xc40`` or ``ex1a``. The Fab base class uses a specific setup directory
based on the concatenation of these names. In the example above, this would be
``site_specific/meto_xc40`` or ``site_specific/meto_ex1a``.
The site and platform can be specified as command line option (see
:ref:`Command Line Options<command_line_options>`). All these
directories are stored under the ``site_specific`` directories
to keep the directory structure cleaner.

If no site name is specified, ``default`` is used as site. And
similarly, if no platform is specified, ``default`` is used as platform
(resulting e.g. in ``site_specific/meto-default`` etc). If neither site
nor platform is specified, the name ``site_specific/default`` is used.

Fab comes with a template for a ``site_specific`` setup. It only
contains setting for the ``default`` site.

.. _use_default_configuration:

Default configuration
---------------------
It is strongly recommended for each application to have a default
configuration file, which will define for example compiler profiles,
and typical compiler flags. Any site-specific configuration file
should then inherit from this default, but can also enhance the
setup done by the default.

.. code-block:: python

    from default.config import Config as DefaultConfig

    class Config(DefaultConfig):
        '''Make intel-classic the default compiler
        '''
        def __init__(self):
            super().__init__()
            tr = ToolRepository()
            tr.set_default_compiler_suite("intel-classic")

            # Add a new compiler to the ToolRepository. It is
            # a compiler wrapper available for ifort and gfortran
            # on this site.
            for ftn in ["ifort", "gfortran"]:
                compiler = tr.get_tool(Category.FORTRAN_COMPILER, ftn)
                tr.add_tool(Tauf90(compiler))


Callbacks in configuration files
--------------------------------
The base class adds several calls to the site-specific
configuration file, allowing site-specific changes to the build
process. These callbacks are described here.

Constructor
~~~~~~~~~~~
The constructor receives no parameter, and happens rather early in the
processing chain (see :ref:`site_and_platform`), i.e. at a stage
where not even all command line options have been defined. Besides
general setting up the object, adding new tools to Fab's
``ToolRepository`` can be done here.

``get_valid_profiles``
----------------------
This method is called by ``FabBase`` when defining the command line options.
It defines the list of valid compilation profile modes. This is used
in setting up Python's ``ArgumentParser`` to only allow valid arguments.

.. automethod:: fab.fab_base.site_specific.default.config.Config.get_valid_profiles
    :noindex:

A well written default configuration file will take newly defined
profiles into account and set them up automatically.
See :ref:`new_compilation_profiles` for an extended example.

``handle_command_line_options``
-------------------------------
This method is called immediately after calling the application-specific
``handle_command_line_options`` method.

.. automethod:: fab.fab_base.site_specific.default.config.Config.handle_command_line_options
    :noindex:

It allows site-specific changes based on the specified command line
options. An example is that selecting a hardware target (``--host``
command line option) like GPU or CPU will require different
compiler options. The following example will store all command
line options of the user, and use them later when setting up the
compiler:

.. code-block:: python

    def handle_command_line_options(self, args: argparse.Namespace) -> None:
        # Keep a copy of the args, so they can be used when
        # initialising compilers
        self._args = args

``update_toolbox``
------------------
The ``update_toolbox`` method is called after the Fab ``ToolBox``
and ``BuildConfig`` objects have been created. All command line
options have been parsed, and selected compilers have been added to
the ``ToolBox``.

.. automethod:: fab.fab_base.site_specific.default.config.Config.update_toolbox
    :noindex:

Here is an example of defining the appropriate compilation profiles
for all compilers and linkers:

.. code-block:: python

    def update_toolbox(self, build_config: BuildConfig) -> None:

        for compiler in (tr[Category.C_COMPILER] +
                         tr[Category.FORTRAN_COMPILER] +
                         tr[Category.LINKER]):
            compiler.define_profile("base", inherit_from="")
            for profile in self.get_valid_profiles():
                compiler.define_profile(profile, inherit_from="base")

This sets up a hierarchy where each of the valid compilation profiles
inherits from a ``base`` profile. And they are defined for all
compilers, even if they might not be available. This will make sure
that using compilation modes work in a Fab compiler wrapper, since
it is possible that the wrapped compiler is not available, i.e.
not in ``$PATH``, but the wrapper is. Additionally, using
``get_valid_profiles`` also means that any additional profiles defined
from a derived class will automatically be created. If a different
hierarchy is requested (e.g. ``memory-profile`` might want to inherit
from ``full-debug``, this needs to be updated in the inheriting
class).

After the profiling modes, a ``default`` class should setup
all compilers (including the various flags for the different
compilation profiles). To continue the example from above,
shown here is the code that uses the saved command line options
from the user to setup flags for an Nvidia compiler:

.. code-block:: python

    def update_toolbox(self, build_config: BuildConfig) -> None:

        setup_nvidia(build_config, self.args)


    def setup_nvidia(build_config: BuildConfig,
                     args: argparse.Namespace) -> None:

        tr = ToolRepository()
        nvfortran = tr.get_tool(Category.FORTRAN_COMPILER, "nvfortran")

        if args.openacc or args.openmp:
            host = args.host.lower()
        else:
            # Neither openacc nor openmp specified
            host = ""

        flags = []
        if args.openacc:
            if host == "gpu":
                flags.extend(["-acc=gpu", "-gpu=managed"])
            else:
                # CPU
                flags.extend(["-acc=cpu"])
        ...
        nvfortran.add_flags(flags, "base")
