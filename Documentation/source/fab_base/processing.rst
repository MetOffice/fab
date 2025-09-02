Processing in the Fab Base Class
================================

This chapter describes the processing of an application script
using the Fab base class.
The knowledge of this process will indicate how a derived, application-specific
build script can overwrite methods to customise the build process.

The full class documentation is at the end of this chapter.

The constructor sets up ultimately the Fab ``BuildConfig`` for the build.
It takes the name of the application as argument. The name of the application
will be used when creating the name of the build directory
and it is also the default ``root_symbol`` when analysing the source code
if the script creates an executable (see :ref:`analyse_step`).

The actual build is then started calling the ``build`` method
of the created script. A typical outline of a build script is
therefore::

    from fab.fab_base import FabBase

    class ExampleBuild(FabBase):
        # Additional methods to be overwritten or added

    if __name__ == '__main__':
        # Adjust logging level as appropriate
        logger = logging.getLogger('fab')
        logger.setLevel(logging.DEBUG)
        example = ExampleBuild(name="example")
        example.build()

The two main steps, construction and building, are described next.

Constructor
-----------
As mentioned, the constructor will ultimately create the Fab
``BuildConfig`` object, which is then used to compile the
application. The setup of this ``BuildConfig`` can be
modified by overwriting the appropriate methods in a derived class,
and site- and platform-specific setup can be done in a site-
and platform-specific configuration script.

.. _site_and_platform:

Defining ``site`` and ``platform``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The method ``define_site_platform_target()`` is first called.
This method parses the arguments provided by the user and looks
only for the options ``--site`` and ``--platform`` - any other
option is for now ignored. These two arguments are then used
to define a ``target`` attribute, which is either ``default``
or in the form ``{site}_{platform}``. This name is used to
identify the directory that contains the site-specific
configuration script to be executed. The following three
property getters can be used to access the values:

.. autoproperty:: fab.fab_base.FabBase.platform
    :noindex:
.. autoproperty:: fab.fab_base.FabBase.site
    :noindex:
.. autoproperty:: fab.fab_base.FabBase.target
    :noindex:

Site-specific Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~
After defining the site and platform, a site- and platform-specific
configuration script is executed (if available). By default, the base
class will try to import a module called ``config`` from the path
``"site_specific/{target}"`` (see :ref:`above<site_and_platform>`
for the definition of ``target``), relative to the directory
in which the application script is located. By overwriting the method
``setup_site_specific_location`` an application can setup its
own directories by adding paths to ``sys.path``.

.. automethod:: fab.fab_base.FabBase.setup_site_specific_location
    :noindex:

If the import is successful, the base class creates an instance of the
``Config`` class from the module. This all happens here:

.. automethod:: fab.fab_base.FabBase.site_specific_setup
    :noindex:

Remember if no site- and no platform-name is specified,
it will import the ``Config`` class from the directory
called ``site_specific/default``.

Chapter :ref:`site_specific_config`
describes this class in more detail. An example for the usage
of site-specific configuration is to add new compilers to
Fab's ``ToolRepository``, or set the default compiler suite for
a site.

.. _define_command_line_options:

Defining command line options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
After executing the site-specific configuration file, a Python
argument parser is created with all command line options in the
method ``define_command_line_options``:

.. automethod:: fab.fab_base.FabBase.define_command_line_options
    :noindex:

This method can be overwritten if an application want to add
additional command line flags. The method gets an optional
Python ``ArgumentParser``: a derived class might want to
provide its own instance to provide a better description
message for the argument parser's help message. See
:ref:`here<better_help_messages>` for an example.

A special case is the definition of compilation profiles (like
``fast-debug`` etc). The base class will query the site-specific
configuration object using ``get_valid_profiles()`` to receive a list
of all valid compilation profile names. This allows each site to
specify its own profile modes.

Parsing command line options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Once all command line options are defined in the parser,
the parsing of the command line options happens in:

.. automethod:: fab.fab_base.FabBase.handle_command_line_options
    :noindex:

The result of the parsing is stored in an attribute, which can
be accessed using the ``args`` property of the script instance.

Again, this method can be overwritten to handle the added
application-specific command line options. 

Once the application's ``handle_command_line_options`` has been
executed, the method with the same name in the site-specific
config file will also be called. It gets the argument namespace
information from Python's ArgumentParser as argument:

.. automethod:: fab.fab_base.site_specific.default.config.Config.handle_command_line_options
    :noindex:

This can be used for further site-specific modifications, e.g.
it might add additional flags for the compiler or linker. 
:ref:`handling_new_command_line_options` shows an example of
doing this.

Defining project name
~~~~~~~~~~~~~~~~~~~~~
By default, the base class will use ``"{name}-{self.args.profile}-$compiler"``
as the name for the project directory, i.e. the name of the
project as specified in the constructor, followed by the compilation
profile and compiler name (``$compiler`` is a Python template parameter
and will be replaced by Fab).

A user script can overwrite ``define_project_name`` and define a
different name:

.. automethod:: fab.fab_base.FabBase.define_project_name
    :noindex:

Here an example where ``-mpi`` is added if MPI has been
enabled on the command line. It calls the base class to
add the compilation profile and compiler name.

.. code-block:: python

    def define_project_name(self, name: str) -> str:

        if self.args.mpi:
            name = name + "-mpi"
        return super().define_project_name(name)


``BuildConfig`` creation
~~~~~~~~~~~~~~~~~~~~~~~~
After parsing the command line options, the base class will first
create a Fab ``ToolBox`` which contains the compiler and
linker selected by the user (see Fab documentation for
details). Then it will create the ``BuildConfig`` object,
providing the ``ToolBox`` and the appropriate command line
options::

    label = f"{name}-{self.args.profile}-$compiler"
    self._config = BuildConfig(tool_box=self._tool_box,
                               project_label=label,
                               verbose=True,
                               n_procs=self.args.nprocs,
                               mpi=self.args.mpi,
                               openmp=self.args.openmp,
                               profile=self.args.profile,
                               )


Building
--------
While Fab provides a very flexible way in which the different phases
of the build process can be executed, the base clas provides a fixed order
in which these steps happen (though of course the user could overwrite
the ``build`` method to provide their own order). If additional
phases need to be inserted into the build process, this can be done
by overwriting the corresponding steps, see :ref:`new_build_phase`
for an example.

The naming of the steps follows the Fab naming, but adds a ``_step``
as suffix to distinguish the methods from the Fab functions.
Typically, an application will need to overwrite at least some
of these methods (for example to specify the source files).
This will require either adding calls to Fab methods, or just
calling the base-class. Details will be provided in each section below.

``grab_files_step``
~~~~~~~~~~~~~~~~~~~
This step is responsible for copying the required source files
into the Fab work space (under the source folder). This method's template
in the base class should not be called, otherwise it will raise an exception,
since any script must specify where to get the source code from. Typically,
in this step various Fab functions are used to get the source files:

``grab_folder``
    Fab's ``grab_folder`` recursively copies a file directory into the fab
    work space. It requires that the source files have been made available
    already, e.g. either as a local working copy, or a checkout from
    a repository.

``git_checkout``
    Fab's ``git_checkout`` checks out a git repository, and puts the files
    into the working directory.

``svn_export``, ``svn_checkout``
    Fab provides these two interfaces to svn, and similar to
    ``git_checkout`` these will either export or checkout a Subversion
    repository.

``grab_archive``
    This wii unpack common archive formats like ``tar``, ``zip``,
    ``tztar`` etc.

``fcm_export``, ``fcm_checkout``
    Compatibility layer to the old fcm configuration. This basically runs
    the corresponding Subversion commands.

A script can obviously use any other Python function to get or create source
files.

``find_source_files_step``
~~~~~~~~~~~~~~~~~~~~~~~~~~
This step is responsible for identifying the source files that are
to be used in the build process. While Fab has the ability to analyse
the source tree and determine the minimal necessary set of files, it
is possible that different versions of the same file would be found
in the source tree (e.g. different version of the same file coming
from different repositories that have been checked out). Since Fab
does not support using the same file name more than once (and
since in general it would lead to inconsistency if the same file
name is used), Fab provides the ability to include or exclude
files from its source directory in the Fab work space.

TODO: link to Fab's documentation

This is typically done by specifying a list of path files. Each
element in this list can be either an ``Exclude`` or an ``Include``
object, indicating that files of a specified pattern should be
included or excluded. An example code:

.. code-block:: python

    path_filters = [
        Exclude('my_folder'),
        Include('my_folder/my_file.F90'),
    ]

These path files are then passed to Fab's ``find_source_files``
function. For example:

.. code-block:: Python

    # Setting up path_filters as shows above
    find_source_files(self.config,
                      path_filters=([Exclude('unit-test', '/test/')] +
                                    path_filters))

This step will not affect any files, it will just set up Fab's
``ArtefactStore`` to be aware of the available source files.

Often, suites will provide FCM configuration that include a long list
of files to exclude (and include) to avoid adding duplicated files
into a complex build environment based on many source repositories.

.. code-block::

    extract.path-excl[um] = / # everything
    extract.path-incl[um] =                              \
        src/atmosphere/AC_assimilation/iau_mod.F90       \
        src/atmosphere/PWS_diagnostics/pws_diags_mod.F90 \
        src/atmosphere/aerosols/aero_params_mod.F90      \
        ...

For convenience during porting, Fab  provides a small tool to
interface with existing FCM configuration files. This tool can read
existing FCM configuration files, and convert the ``path-incl`` and
``path-excl`` directives into Fab's ``Exclude`` and ``Include``
objects. Example usage:

.. code-block:: python

        extract_cfg = FcmExtract(self.lfric_apps_root / "build" / "extract" /
                                  "extract.cfg")

        science_root = self.config.source_root / 'science'
        path_filters = []
        for section, source_file_info in extract_cfg.items():
            for (list_type, list_of_paths) in source_file_info:
                if list_type == "exclude":
                    # Exclude in this application removes the whole
                    # app (so that individual files can then be picked
                    # using include)
                    path_filters.append(Exclude(science_root / section))
                else:
                    # Remove the 'src' which is the first part of the name
                    # in this script, which we don't have here
                    new_paths = [i.relative_to(i.parents[-2])
                                 for i in list_of_paths]
                    for path in new_paths:
                        path_filters.append(Include(science_root /
                                                    section / path))

``define_preprocessor_flags_step``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This method is called before preprocessing, and it allows the application
to specify all flags required for preprocessing all C, and Fortran files.

.. automethod:: fab.fab_base.FabBase.define_preprocessor_flags_step
    :noindex:

The base class provides its own method of adding preprocessor flags:

.. automethod:: fab.fab_base.FabBase.add_preprocessor_flags
    :noindex:

Flags can be specified either as a single flag, or as a list of flags.
Each flag can either be a simple string, which is a command line option
for the compiler, or a path-specific flag using Fab's ``AddFlags``
class (TODO: link to fab). Example code:

.. code-block:: python

    def define_preprocessor_flags(self):
        super().define_preprocessor_flags()

        self.add_preprocessor_flags(['-DUM_PHYSICS',
                                     '-DCOUPLED',
                                     '-DUSE_MPI=YES'])

        path_flags = [AddFlags(match="$source/science/jules/*",
                               flags=['-DUM_JULES', '-I$output']),
                      AddFlags(match="$source/large_scale_precipitation/*",
                               flags=['-I$relative/include',
                                      '-I$source/science/shumlib/common/src'])]

        self.add_preprocessor_flags(path_flags)
        # Add a preprocessor flag depending on compilation profile:
        if self.args.profile == "full-debug":
            self.add_preprocessor_flags("-DDEBUG")

``preprocess_c_step``
~~~~~~~~~~~~~~~~~~~~~
There is usually no reason to overwrite this method. It will use
the preprocessor flags defined in the previous
``define_preprocessor_flags_step`` and preprocess
all C files.

.. automethod:: fab.fab_base.FabBase.preprocess_c_step
    :noindex:

``preprocess_fortran_step``
~~~~~~~~~~~~~~~~~~~~~~~~~~~
There is usually no reason to overwrite this method. It will use
the preprocessor flags defined in the previous
``define_preprocessor_flags_step`` and preprocess
all Fortran files.

.. automethod:: fab.fab_base.FabBase.preprocess_fortran_step
    :noindex:

.. _analyse_step:

``analyse_step``
~~~~~~~~~~~~~~~~
This steps does the complete dependency analysis for the application.
There is usually no reason for an application to overwrite this step.

In case of creating a binary, the analyse step will use the root symbol,
which defaults to the name of the application, but can be changed
using ``set_root_symbol``. This implies that ``set_root_symbol``
must be called before ``analyse_step`` is called, e.g. it can be called
from any method called from the constructor (including defining and
handling command line options).

.. automethod:: fab.fab_base.FabBase.analyse_step
    :noindex:

``compile_c_step``
~~~~~~~~~~~~~~~~~~
This step compiles all C files. There is usually no reason for an
application to overwrite this step.

.. automethod:: fab.fab_base.FabBase.compile_c_step
    :noindex:

``compile_fortran_step``
~~~~~~~~~~~~~~~~~~~~~~~~
This step compiles all Fortran files. As it takes a list of path-specific
flags as an argument, child classes can overwrite this method to pass
additional path-specific flags.

.. automethod:: fab.fab_base.FabBase.compile_fortran_step
    :noindex:

``archive_objects``
~~~~~~~~~~~~~~~~~~~
This step creates an archive with all compiled object files.

.. warning::

    Due to https://github.com/MetOffice/fab/issues/310
    it is not recommended to create archives. Therefore, this
    step is for now not executed at all!

``link_step``
~~~~~~~~~~~~~
This step links all required object files into the executable
or library. There is usually no reason for an application to overwrite
this method.

.. automethod:: fab.fab_base.FabBase.link_step
    :noindex:
