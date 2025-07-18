.. _Advanced Config:

Advanced Configuration
**********************

A lot can be achieved with simple configurations but some of the more esoteric
aspects of software building may require more esoteric Fab features.


.. _env_vars:

Understanding the Environment
=============================
Fab itself does not support any environment variables. But a user
script can obviously query the environment and make use of environment
variables, and provide their values to Fab.

Configuration Reuse
===================

If you find you have multiple build configurations with duplicated code, it
could be helpful to factor out the commonality into a shared module. Remember,
your build configuration is just a Python script at the end of the day.

In Fab's
`example configurations <https://github.com/metomi/fab/tree/master/run_configs>`_,
we have two build scripts to compile GCOM. Much of the configuration for these
two scripts is identical. We extracted the common steps into
`gcom_build_steps.py <https://github.com/metomi/fab/blob/master/run_configs/gcom/gcom_build_steps.py>`_
and used them in
`build_gcom_ar.py <https://github.com/metomi/fab/blob/master/run_configs/gcom/build_gcom_ar.py>`_
and
`build_gcom_so.py <https://github.com/metomi/fab/blob/master/run_configs/gcom/build_gcom_so.py>`_.


Separate grab and build scripts
===============================
If you are running many builds from the same source, you may wish to grab your
repo in a separate script and call it less frequently.

In this case your grab script might only contain a single step. You could
import your grab configuration to find out where it put the source.

.. code-block::
    :linenos:
    :caption: my_grab.py

    my_grab_config = BuildConfig(project_label='<project_label>')

    if __name__ == '__main__':
        with my_grab_config:
            fcm_export(my_grab_config, src='my_repo')


.. code-block::
    :linenos:
    :caption: my_build.py
    :emphasize-lines: 6

    from my_grab import my_grab_config


    if __name__ == '__main__':
        with BuildConfig(project_label='<project_label>') as state:
            grab_folder(state, src=my_grab_config.source_root),


Housekeeping
============

You can add a :func:`~fab.steps.cleanup_prebuilds.cleanup_prebuilds`
step, where you can explicitly control how long to keep prebuild files.
This may be useful, for example, if you often switch between two versions
of your code and want to keep the prebuild speed benefits when building
both.

If you do not add your own cleanup_prebuild step, Fab will
automatically run a default step which will remove old files from the
prebuilds folder. It will remove all prebuild files that are not part of
the current build by default.


Sharing Prebuilds
=================

You can copy the contents of someone else's prebuilds folder into your own.

Fab uses hashes to keep track of the correct prebuilt files, and will find and
use them. There's also a helper step called
:func:`~fab.steps.grab.prebuild.grab_pre_build` you can add to your build
configurations.


PSyKAlight (PSyclone overrides)
===============================

If you need to override a PSyclone output file with a handcrafted version
you can use the ``overrides_folder`` argument to the
:func:`~fab.steps.psyclone.psyclone` step.

This specifies a normal folder containing source files. The step will delete
any files it creates if there's a matching filename in the overrides folder.


Two-Stage Compilation
=====================

The :func:`~fab.steps.compile_fortran.compile_fortran` step compiles files in
 passes, with each pass identifying all the files which can be compiled next,
 and compiling them in parallel.

Some projects have bottlenecks in their compile order, where lots of files are
stuck behind a single file which is slow to compile. Inspired by
`Busby <https://www.osti.gov/biblio/1393322>`_, Fab can perform two-stage
compilation where all the modules are built first in *fast passes* using the
`-fsyntax-only` flag, and then all the slower object compilation can follow in
a single pass.

The *potential* benefit is that the bottleneck is shortened, but there is a
tradeoff with having to run through all the files twice. Some compilers might
not have this capability.

Two-stage compilation is configured with the `two_stage_flag` argument to the
Fortran compiler.

.. code-block::
    :linenos:

    compile_fortran(state, two_stage_flag=True)


Managed arguments
=================

As noted above, Fab manages a few command line arguments for some of the tools
it uses.

Fortran Preprocessors
---------------------

Fab knows about some preprocessors which are used with Fortran, currently *fpp*
and *cpp*. It will ensure the ``-P`` flag is present to disable line numbering
directives in the output, which is currently required for fparser to parse the
output.

Fortran Compilers
-----------------

Fab knows about some Fortran compilers (currently *gfortran* or *ifort*).
It will make sure the `-c` flag is present to compile but not link.

If the compiler flag which sets the module folder is present, i.e. ``-J`` for
gfortran or ``-module`` for ifort, Fab will **remove** the flag, with a
notification, as it needs to use this flag to control the output location.


.. _Advanced Flags:

Compilation Profiles
====================
Fab supports compilation profiles. A compilation profile is essentially a simple
string that represents a set of compilation and linking flags to be used.
For example, an application might have profiles for `full-debug`, `fast-debug`,
and `production`. Compilation profiles can inherit settings, for example
`fast-debug` might inherit from `full-debug`, but add optimisations.
Compilation profile names are not case sensitive.

Any flag for any tool can make use of a profile, but in many cases this is
not necessary (think of options for ``rsync``, ``git``, ``svn``, ...). Fab will
internally create a dummy profile, indicated by an empty string `""`. If no
profile is specified, this default profile will be used.

A profile is defined as follows:

.. code-block::
    :linenos:

    tr = ToolRepository()
    gfortran = tr.get_tool(Category.FORTRAN_COMPILER, "gfortran")

    gfortran.define_profile("base")
    gfortran.define_profile("fast-debug", inherit_from="base")
    gfortran.define_profile("full-debug", inherit_from="fast-debug")

    gfortran.add_flags(["-g", "-std=f2008"], "base")
    gfortran.add_flags(["-O2"], "fast-debug")
    gfortran.add_flags(["-O0", "-fcheck=all"], "full-debug")

Line 3 defines a profile called ``base``, which does not inherit from any
other profile. Next, a profile ``fast-debug`` is defined, which is based
on ``base``. It will add the flags ``-O2`` to the command line, together
with the inherited flags from base, it will be using ``-g -std=f2008 -O2``
Finally, a ``full-debug`` profile is declared, based on ``fast-debug``.
Due to the inheritance, it will be using the options
``-g -std=f2008 -O2 -O0 -fcheck=all``. Note that because of the precedence
of compiler flags, the no-optimisation flag ``-O0`` will overwrite the
valued of ``-O2``.

Tools that do not require a profile can omit the parameter
when defining flags:

.. code-block::
    :linenos:

    git = config.tool_box[Category.GIT]
    git.add_flags(["-c", "foo.bar=123"])

This effectively adds the flags to the to the dummy profile, allowing
them to be used by other Fab functions.

By default, the dummy profile ``""`` is not used as a base class for
any other profile. But it can be convenient to set this up to make
user scripts slightly easier. Here is an example of the usage
in LFRic, where at startup time a consistent set of profile modes are
defined for each compiler and linker:

.. code-block::
    :linenos:

    tr = ToolRepository()
    for compiler in (tr[Category.C_COMPILER] +
                     tr[Category.FORTRAN_COMPILER] +
                     tr[Category.LINKER]):
        compiler.define_profile("base", inherit_from="")
        for profile in ["full-debug", "fast-debug", "production"]:
            compiler.define_profile(profile, inherit_from="base")

Line 5 defines a ``base`` profile, which inherits from the dummy
profile. Then a set of three profiles are defined, each
inheriting from ``base``, and therefore in turn from the dummy profile.

Later, the Intel Fortran compiler and linker ``ifort`` are setup as follows:

.. code-block::
    :linenos:

    tr = ToolRepository()
    ifort = tr.get_tool(Category.FORTRAN_COMPILER, "ifort")
    ifort.add_flags(["-stand", "f08"],           "base")
    ifort.add_flags(["-g", "-traceback"],        "base")
    ifort.add_flags(["-O0", "-ftrapuv"],         "full-debug")
    ifort.add_flags(["-O2", "-fp-model=strict"], "fast-debug")
    ifort.add_flags(["-O3", "-xhost"],           "production")

    linker = tr.get_tool(Category.LINKER, "linker-ifort")
    linker.add_lib_flags("yaxt", ["-lyaxt", "-lyaxt_c"])
    linker.add_post_lib_flags(["-lstdc++"])

The setup of the compiler does not use the dummy profile at all,
so it will stay empty. It is up to the user to decide how to use the
profiles, it would be entirely valid not to use the ``base`` profile, but
instead to use the dummy. But when setting up the linker, no profile is specified.
So line 10 and 11 will set these flags for the dummy. Because of ``base``
inheriting from the dummy, and any other profile inheriting from ``base``,
this means these linker flags will be used for all profiles. It would
be equally valid to define these flags for the ``base`` profile:

.. code-block::
    :linenos:

    linker = tr.get_tool(Category.LINKER, "linker-ifort")
    linker.add_lib_flags("yaxt", ["-lyaxt", "-lyaxt_c"], "base")
    linker.add_post_lib_flags(["-lstdc++"], "base")

This design was chosen because the most common use case for
profiles involves changing compiler flags. Linker flags are typically
left unaltered, so it is more intuitive for a user to omit profile modes
for the linker.

The advantage of supporting the profile modes for linker is that
you can specify profile modes that require additional linking options.
One example is GNU's address sanitizer, which requires to
add the compilation option ``-fsanitize=address``, and the linker option
``-static-libasan``.

.. code-block::
    :linenos:

    tr = ToolRepository()
    gfortran = tr.get_tool(Category.FORTRAN_COMPILER, "gfortran")
    ...
    gfortran.define_profile("memory-debug", "full-debug")
    gfortran.add_flags(["-fsanitize=address"], "memory-debug")
    linker = tr.get_tool(Category.LINKER, "linker-gfortran")
    linker.add_post_lib_flags(["-static-libasan"], "memory-debug")

This way, by just changing the profile, compilation and linking
will be affected consistently.


Tool arguments
============== 

Sometimes it is necessary to pass additional arguments when we call a software
tool.

Linker flags
------------

Probably the most common instance of the need to pass additional arguments is
to specify 3rd party libraries at the link stage. The linker tool allow
for the definition of library-specific flags: for each library, the user can
specify the required linker flags for this library. In the linking step,
only the name of the libraries to be linked is then required. The linker
object will then use the required linking flags. Typically, a site-specific
setup set (see for example https://github.com/MetOffice/lfric-baf) will
specify the right flags for each site, and the application itself only
needs to list the name of the libraries. This way, the application-specific
Fab script is independent from any site-specific settings. Still, an
application-specific script can also overwrite any site-specific setting,
for example if a newer version of a dependency is to be evaluated.

The settings for a library are defined as follows:

.. code-block::
    :linenos:

        tr = ToolRepository()
        linker = tr.get_tool(Category.LINKER, "linker-ifort")

        linker.add_lib_flags("yaxt", ["-L/some_path", "-lyaxt", "-lyaxt_c"])
        linker.add_lib_flags("xios", ["-lxios"])

This will define two libraries called ``yaxt`` and ``xios``. In the link step,
the application only needs to specify the name of the libraries required, e.g.:

.. code-block::
    :linenos:

    link_exe(state, libs=["yaxt", "xios"])

The linker will then use the specified options.

A linker object also allows to define options that should always be added,
either as options before any library details, or at the very end. For example:

.. code-block::
    :linenos:

        linker.add_pre_lib_flags(["-L/my/common/library/path"])
        linker.add_post_lib_flags(["-lstdc++"])

The pre_lib_flags can be used to specify library paths that contain
several libraries only once, and this makes it easy to evaluate a different
set of libraries. Additionally, this can also be used to add common
linking options, e.g. Cray's ``-Ktrap=fp``.

The post_lib_flags can be used for additional common libraries that need
to be linked in. For example, if the application contains a dependency to
C++ but it is using the Fortran compiler for linking, then the C++ libraries
need to be explicitly added. But if there are several libraries depending
on it, you would have to specify this several times (forcing the linker to
re-read the library several times). Instead, you can just add it to the
post flags once.

The linker step itself can also take optional flags:

.. code-block::
    :linenos:

    link_exe(state, flags=['-Ktrap=fp'])

These flags will be added to the very end of the the linker options,
i.e. after any other library or post-lib flag. Note that the example above is
not actually recommended to use, since the specified flag is only
valid for certain linker, and a Fab application script should in general
not hard-code flags for a specific linker. Adding the flag to the linker
instance itself, as shown further above, is the better approach.


Path-specific flags
-------------------

For preprocessing and compilation, we sometimes need to specify flags
*per-file*. These steps accept both common flags and *path specific* flags.

.. code-block::
    :linenos:

    ...
    compile_fortran(
        common_flags=['-O2'],
        path_flags=[
            AddFlags('$output/um/*', ['-I' + '/gcom'])
        ],
    )

This will add ``-O2`` to every invocation of the tool, but only add the
``*/gcom*`` include path when processing files in the
``*<project workspace>/build_output/um*`` folder.

Path matching is done using Python's `fnmatch <https://docs.python.org/3.10/library/fnmatch.html#fnmatch.fnmatch>`_.
The ``$output`` is a template, see :class:`~fab.build_config.AddFlags`.

We can currently only *add* flags for a path.

.. note::
    This can require some understanding of where and when files are placed in
    the *build_output* folder: It will generally match the structure you've
    created in ``*<project workspace>/source*``, with your grab steps.
    
    Early steps like preprocessors generally read files from ``*source*`` and
    write to ``*build_output*``.
    
    Later steps like compilers generally read files which are already in
    ``*build_output*``.
    
    For more information on where files end up see :ref:`Directory Structure`.


.. _Directory Structure:

Folder Structure
================

It may be useful to understand how Fab uses the :term:`Project Workspace` and
in particular where it creates files within it.

.. code-block::

    <your $FAB_WORKSPACE>
       <project workspace>
          source/
          build_output/
             *.f90 (preprocessed Fortran files)
             *.mod (compiled module files)
             _prebuild/
                *.an (analysis results)
                *.o (compiled object files)
                *.mod (mod files)
          metrics/
          my_program
          log.txt

The *project workspace* folder takes its name from the project label passed in to the build configuration.

The *source* folder is where grab steps place their files.

The *build_output* folder is where steps put their processed files.
For example, a preprocessor reads ``.F90`` from *source* and writes ``.f90`` to *build_output*.

The *_prebuild* folder contains reusable output. Files in this folder include a hash value in their filenames.

The *metrics* folder contains some useful stats and graphs. See :ref:`Metrics`.


.. _C Pragma Injector:

C Pragma Injector
=================

The C pragma injector creates new C files with ``.prag`` file extensions, in the
source folder. The C preprocessor looks for the output of this step by default.
If not found, it will fall back to looking for ``.c`` files in the source
listing.

.. code-block::
    :linenos:

    ...
    c_pragma_injector(state)
    preprocess_c(state)
    ...


.. _Custom Steps:

Custom Steps
============
If you need a custom build step, you can create a function with the @step
decorator.

Some example custom steps are included in the Fab testing configurations. For
example a simple example was created for building JULES.

The :func:`~fab.steps.root_inc_files.root_inc_files` step copies all ``.inc``
files in the source tree into the root of the source tree, to make subsequent
preprocessing flags easier to configure.

That is a simple example that doesn't need to interact with the
:term:`Artefact Store`. Sometimes inserting a custom step means inserting a new
:term:`Artefact Collection` into the flow of data between steps.

We can tell a subsequent step to read our new artefacts, instead of using it's
default :term:`Artefacts Getter`. We do this using the ``source`` argument,
which most Fab steps accept. (See :ref:`Overriding default collections`)

.. code-block::
    :linenos:

    @step
    def custom_step(state):
        state.artefact_store['custom_artefacts'] = do_something(state.artefact_store['step 1 artefacts'])


    with BuildConfig(project_label='<project label>') as state:
        fab_step1(state)
        custom_step(state)
        fab_step2(state, source=CollectionGetter('custom_artefacts'))


Steps have access to multiprocessing methods through the
:func:`~fab.steps.run_mp` helper function. This processes artefacts in parallel.

.. code-block::
    :linenos:

    @step
    def custom_step(state):
        input_files = state.artefact_store['custom_artefacts']
        results = run_mp(state, items=input_files, func=do_something)


.. _Overriding default collections:

Collection names
================

Most steps allow the collections they read from and write to to be changed.

Let's imagine we need to upgrade a build script, adding a custom step to
prepare our Fortran files for preprocessing.

.. code-block::
    :linenos:

    find_source_files(state)  # this was already here

    # instead of this
    # preprocess_fortran(state)

    # we now do this
    my_new_step(state, output_collection='my_new_collection')
    preprocess_fortran(state, source=CollectionGetter('my_new_collection'))

    analyse(state)  # this was already here


Parser Workarounds
==================

Sometimes the parser used by Fab to understand source code can be unable to
parse valid source files due to bugs or shortcomings. In order to still be able
to build such code a number of possible work-arounds are presented.

.. _Unrecognised Deps Workaround:

Unrecognised Dependencies
-------------------------

If a language parser is not able to recognise a dependency within a file,
then Fab won't know the dependency needs to be compiled.

For example, some versions of fparser don't recognise a call on a one-line if
statement.

We can manually add the dependency using the `unreferenced_deps` argument to
:func:`~fab.steps.analyse.analyse`.

Pass in the name of the called function. Fab will find the file containing this
symbol and add it, *and all its dependencies*, to every :term:`Build Tree`.

.. code-block::
    :linenos:

    ...
    analyse(state, root_symbol='my_prog', unreferenced_deps=['my_func'])
    ...

Unparsable Files
----------------

If a language parser is not able to process a file at all, then Fab won't know
about any of its symbols and dependencies. This can sometimes happen to *valid
code* which compilers *are* able to process, for example if the language parser
is still maturing and can't yet handle an uncommon syntax.

In this case we can manually give Fab the analysis results using the
`special_measure_analysis_results` argument to
:func:`~fab.steps.analyse.analyse`.

Pass in a list of :class:`~fab.parse.fortran.FortranParserWorkaround` objects,
one for every file that can't be parsed. Each object contains the symbol
definitions and dependencies found in one source file.

.. code-block::
    :linenos:

    ...
    analyse(
        config,
        root_symbol='my_prog',
        special_measure_analysis_results=[
            FortranParserWorkaround(
                fpath=Path(state.build_output / "path/to/file.f90"),
                module_defs={'my_mod'}, symbol_defs={'my_func'},
                module_deps={'other_mod'}, symbol_deps={'other_func'}),
        ])
    ...

In the above snippet we tell Fab that ``file.f90`` defines a module called
``my_mod`` and a function called ``my_func``, and depends on a module called
``other_mod`` and a function called ``other_func``.

Custom Step
^^^^^^^^^^^

An alternative approach for some problems is to write a custom step to modify
the source so that the language parser can process it. Here's a simple example,
based on a
`real workaround <https://github.com/metomi/fab/blob/216e00253ede22bfbcc2ee9b2e490d8c40421e5d/run_configs/um/build_um.py#L42-L65>`_
where the parser gets confused by a variable called `NameListFile`.

.. code-block::
    :linenos:

    @step
    def my_custom_code_fixes(state):
        fpath = state.source_root / 'path/to/file.F90'
        in = open(fpath, "rt").read()
        out = in.replace("NameListFile", "MyRenamedVariable")
        open(fpath, "wt").write(out)

    with BuildConfig(project_label='<project_label>') as state:
        # grab steps first
        my_custom_code_fixes(state)
        # find_source_files, preprocess, etc, afterwards

A more detailed treatment of :ref:`Custom Steps` is given elsewhere.
