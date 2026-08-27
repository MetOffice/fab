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
~~~~~~~~~~~~~~~~~~~~~~
This method is called by ``FabBase`` when defining the command line options.
It defines the list of valid compilation profile modes. This is used
in setting up Python's ``ArgumentParser`` to only allow valid arguments.

.. automethod:: fab.fab_base.site_specific.default.config.Config.get_valid_profiles
    :noindex:

A well written default configuration file will take newly defined
profiles into account and set them up automatically.
See :ref:`new_compilation_profiles` for an extended example.

``handle_command_line_options``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
~~~~~~~~~~~~~~~~~~
The ``update_toolbox`` method is called after the Fab ``ToolBox``
and ``BuildConfig`` objects have been created. All command line
options have been parsed, and selected compilers have been added to
the ``ToolBox``.

.. automethod:: fab.fab_base.site_specific.default.config.Config.update_toolbox
    :noindex:

Here is an example of defining the appropriate compilation profiles
for all compilers and linkers:

.. code-block:: python

    from fab.api import ProfileFlags

    def update_toolbox(self, build_config: BuildConfig) -> None:

        ProfileFlags.define_profile("base")
        for profile in self.get_valid_profiles():
            ProfileFlags.define_profile(profile, inherit_from="base")

This sets up a hierarchy where each of the valid compilation profiles
inherits from a ``base`` profile. Using ``get_valid_profiles`` also means
that any additional profiles defined from a derived class will automatically
be created. If a different hierarchy is requested (e.g. ``memory-profile``
might want to inherit from ``full-debug``, this needs to be updated in the
inheriting class).

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


Tools for site-specific configurations
--------------------------------------
Fab provides some tool to simplify writing site-specific configuration
files:

``NfConfig``
~~~~~~~~~~~~
The ``NfConfig`` class uses NetCDF's ``nf-config`` to query for compilation
and linking flags. Usage:

.. code-block:: python
    
    from fab.tools.nf_config import NfConfig

    tr = ToolRepository()
    linker = tr.get_tool(Category.LINKER, f"linker-{gfortran.name}")
    linker = cast(Linker, linker)

    nf_config = NfConfig()
    linker.add_lib_flags("netcdf", nf_config.get_linker_flags())

    netcdf_compiler_flags = nf_config.get_compiler_flags()

``PkgConfig``
~~~~~~~~~~~~~
This class provides a simple interface to ``pkg-config``.
Usage:

.. code-block:: python

    from fab.tools.pkg_config import PkgConfig

    tr = ToolRepository()
    linker = tr.get_tool(Category.LINKER, f"linker-{gfortran.name}")
    linker = cast(Linker, linker)

    pkg_netcdf = PkgConfig("netcdf-fortran")
    linker.add_lib_flags("netcdf", pkg_netcdf.get_linker_flags())

    netcdf_compiler_flags = pkg_netcdf.get_compiler_flags()

Note that at this stage no support for version numbers or version
checking has been added.


``Shell``
~~~~~~~~~
This class provides a simple interface to a shell, and it can be
used to easily start other scripts and use their output to set
flags. It takes the name of the shell as parameter. The `ToolRepository``
contains a ready-to-go instance for ``sh``, but you can create an
instance that uses other shells. Usage:

.. code-block:: python

    from fab.tools.shell import Shell

    # Get the pre-created `sh` shell:
    shell = tr.get_default(Category.SHELL)

    bash = Shell("bash")

    try:
        # We must remove the trailing new line, and create a list:
        nc_flibs = shell.run(additional_parameters=["-c", "nf-config --flibs"],
                             capture_output=True).strip().split()
    except RuntimeError:
        nc_flibs = []

    linker.add_lib_flags("netcdf", nc_flibs)

Application-specific settings
=============================
Besides site-specific settings, the Fab base class also allows
application-specific setups, which can work together with site-specific
configurations using inheritance. These config files are the same
as site-specific configuration files described previously, but are
imported from the directory ``app_specific``.

An example of this is LFRic. The infrastructure (lfric_core) repository
contains site-specific configuration. For example, they will define
the required compilation flags for files. These settings will be used
even for applications in the lfric_apps repository.
But certain applications needs additional flags. For example, the
lfric_atm application will compile the UM physics code, and this require
that by default any real values are double precision (and in some cases
file-specific work arounds for compiler bugs). To avoid that the site-settings
from lfric_core need to be duplicated. The following structure is
recommended (and used in lfric_atm), in this example for the site
`nci` on the platform `gadi` - the arrows indicating an 'inherit from'
relationship::

     SiteConfig/default  <-  AppConfig/default
           ^                          ^
           |                          |
     SiteConfig/NciGadi  <-  AppConfig/NciGadi

At start up, the application-specific configuration for the specified site
will be read in. The Python method resolution order then guarantees that
any ``super()`` access will first call ``AppConfig/default``, which will
then call ``SiteConfig/NciGadi``, and then ``SiteConfig/default``.

In Python code, this looks as follows:

``app_specific/nci_gadi``:

.. code-block:: python

    from app_specific.default.config import Config as ConfigAppDefault
    from site_specific.nci_gadi.config import Config as ConfigSiteNciGadi

    class Config(ConfigAppDefault, ConfigSiteNciGadi):
        def __init__(self):
            super().__init__()

``app_specific/default:``

.. code-block:: python

    from site_specific.default.config import Config as ConfigSiteDefault

    class Config(ConfigSiteDefault):
        def __init__(self):
            super().__init__()
            
``site_specific/nci_gadi:``

.. code-block:: python

    from site_specific.default.config import Config as ConfigSiteDefault

    class Config(ConfigSiteDefault):
        def __init__(self):
            super().__init__()

``site_specific/default:``

.. code-block:: python

    class Config:
        def __init__(self):
            ...
                
This setup will allow us to reuse site-specific setup, which can be overwritten
by application-specific settings. As an example of what to do on what level:

1. ``site_specific/default`` would define optimisation levels (depending on profile)
2. ``site_specific/nci_gadi`` could add flags for more thorough full-debug tests.
   It would also contain all required library definitions.
3. ``app_specific/default`` would add flags for compiling UM (e.g. 8 byte default reals)
4. ``app_specific/nci_gadi`` could add additional compiler optimisation flags for
   certain files, which are beneficial for the resolution usually used at NCI. Also,
   if an application needs additional libraries, they can be added here.

The usage of ``nci_gadi`` means that additional compiler flags can easily be
added, since it will only affect runs on NCI. If a flag would be useful for
any site (e.g. to work around a compiler bug), this flag would eventually be moved
into the ``default`` setup.

.. important::
    If there is an application-specific configuration, it is important that
    each site specifies its own application-specific setup. Otherwise only
    the site-specific configuration would be used (since the import from
    ``app_specific/SITE`` fails, which means that the application specific
    setup would not be executed at all).
