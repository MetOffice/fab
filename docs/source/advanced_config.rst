.. _Advanced Config:

Advanced Config
***************

Folder structure
================
Fab creates files in the :term:`Project Workspace`.

| <your $FAB_WORKSPACE>
|    **<project workspace>**
|       source/
|       build_output/
|          \*.f90 (preprocessed Fortran files)
|          \*.mod (compiled module files)
|          _prebuild/
|             \*.an (analysis results)
|             \*.o (compiled object files)
|             \*.mod (mod files)
|       metrics/
|       my_program.exe
|       log.txt
|

The *project workspace* folder takes its name from the project label passed in to the build config.

The *source* folder is where grab steps place their files.

The *build_output* folder is where steps put their processed files.
For example, a preprocessor reads ``.F90`` from *source* and writes ``.f90`` to *build_output*.

The *_prebuild* folder contains reusable output. Files in this folder include a hash value in their filenames.

The *metrics* folder contains some useful stats and graphs. See :ref:`Metrics`.



Managed arguments
=================
Fab manages a few command line arguments for some of the tools it uses.

Fortran Preprocessors
---------------------
Fab knows about some preprocessors which are used with Fortran, currently *fpp* and *cpp*.
It will ensure the ``-P`` flag is present to disable line numbering directives in the output,
which is currently required for fparser to parse the output.

Fortran Compilers
-----------------
Fab knows about some Fortran compilers (currently *gfortran* or *ifort*).
It will make sure the `-c` flag is present to compile only (not link).

If the compiler flag which sets the module folder is present,
i.e. ``-J`` for gfortran or ``-module`` for ifort,
Fab will **remove** the flag, with a notification,
as it needs to use this flag to control the output location.


.. _Overriding default collections:

Overriding defaults
===================

Command line tools
------------------
Fab uses well-known environment variables for tool configuration.

.. list-table:: Environment variables
   :widths: 10 30

   * - FPP
     - Fortran preprocessor, e.g ``fpp`` or ``cpp -traditional-cpp -P``.
       Fab ensures the ``-P`` is present.
   * - FC
     - Fortran compiler, e.g ``gfortran`` or ``ifort -c``.
       Fab ensures the ``-c`` is present.
   * - FFLAGS
     - Fortran compiler flags.
   * - CC
     - C compiler.
   * - CFLAGS
     - C compiler flags.
   * - LD
     - Linker, e.g ``ld``.
   * - LFLAGS
     - Linker flags.


Collection names
----------------
You can change the collections which most steps read from and write to.
Let's imagine we need to upgrade a build script, adding a custom step to prepare our Fortran files for preprocessing.

.. code-block::
    :linenos:

    FindSourceFiles()  # this was already here

    # instead of this
    # fortran_preprocessor()

    # we now do this
    my_new_step(output_collection='my_new_collection')
    fortran_preprocessor(source=CollectionGetter('my_new_collection'))

    Analyse()  # this was already here


.. _Advanced Flags:

Flags
=====

Linker flags
------------
We can add flags to our linker step.

.. code-block::
    :linenos:

    steps=[
        ...
        LinkExe(flags=['-lm', '-lnetcdf']),
    ]

Path-specific flags
-------------------
For preprocessing and compilation, we sometimes need to specify flags *per-file*.
These steps accept both common flags and *path specific* flags.

.. code-block::

    steps=[
        ...
        CompileFortran(
            common_flags=['-O2'],
            path_flags=[
                AddFlags('$output/um/*', ['-I' + '/gcom'])
            ],
        ),
    ]

This will add `-O2` to every invocation of the tool, but only add the */gcom* include path when processing
files in the *<project workspace>/build_output/um* folder.

Path matching is done using Python's `fnmatch <https://docs.python.org/3.10/library/fnmatch.html#fnmatch.fnmatch>`_.
The ``$output`` is a template, see :class:`~fab.build_config.AddFlags`.

We can currently only *add* flags for a path.
Future development could add capability to *remove* or *modify* flags by path.

.. note::
    This can require some understanding of where and when files are placed in the *build_output* folder:
    It will generally match the structure you've created in *<project workspace>/source*, with your grab steps.
    Early steps like preprocessors generally read files from *source* and write to *build_output*.
    Later steps like compilers generally read files which are already in *build_output*.


.. _Advanced C Code:

C Code
======
The C pragma injector creates new C files with ".prag" file extensions, in the source folder.
The C preprocessor looks for the output of this step by default.
If not found, it will fall back to looking for .c files in the source listing.

.. code-block::

        steps = [
            ...
            CPragmaInjector(),
            c_preprocessor(),
            ...
        ]


Custom Steps
============
If you need a custom build step, you can create a subclass of the :class:`~fab.steps.Step` class.

Fab includes some examples of a custom step. A simple example was created for building JULES.
The :class:`~fab.steps.root_inc_files.RootIncFiles` step copies all `.inc` files in the source tree
into the root of the source tree, to make subsequent preprocessing flags easier to configure.

That was a simple example that didn't need to interact with the :term:`Artefact Store`.
Sometimes, inserting a custom step means inserting a new :term:`Artefact Collection` into the flow of data between
steps. We can tell a subsequent step to read our new artefacts, instead of using it's default :term:`Artefacts Getter`.
We do this using the `source` argument, which most Fab steps accept.

.. code-block::

    class CustomStep(Step):
        def run(self, artefact_store: Dict, config):
            artefact_store['custom_artefacts'] = do_something(artefact_store['step 1 artefacts'])


    config = BuildConfig('my_proj', steps=[
        FabStep1(),
        CustomStep(),
        FabStep2(source=CollectionGetter('custom_artefacts')),
    ])


Steps have access to multiprocessing methods.
The Step class includes a multiprocessing helper method called :meth:`~fab.steps.Step.run_mp` which steps can call
from their :meth:`~fab.steps.Step.run` method to process a collection of artefacts in parallel.

.. code-block::

    class CustomStep(Step):
        def run(self, artefact_store: Dict, config):
            input_files = artefact_store['custom_artefacts']
            results = self.run_mp(items=input_files, func=do_something)


Parser Workarounds
==================

.. _Unrecognised Deps Workaround:

Unrecognised Dependencies
-------------------------
If a language parser is not able to recognise a dependency within a file,
then Fab won't know the dependency needs to be compiled.
For example, some versions of fparser don't recognise a call on a one-line if statement.
In this case we can manually add the dependency using the `unreferenced_deps` argument to
:class:`~fab.steps.analyse.Analyse`.

Pass in the name of the called function.
Fab will find the file containing this symbol and add it, *and all its dependencies*, to the build.

.. code-block::
    :linenos:

    config.steps = [
        ...
        Analyse(root_symbol='my_prog', unreferenced_deps=['my_func'])
        ...
    ]

Unparsable Files
----------------
If a language parser is not able to process a file at all,
then Fab won't know about any of its symbols and dependencies.
This can sometimes happen to *valid code* which compilers *are* able to process,
for example if the language parser is still maturing and can't yet handle an uncommon syntax.
In this case we can manually give Fab the analysis results
using the `special_measure_analysis_results` argument to :class:`~fab.steps.analyse.Analyse`.

Pass in a list of :class:`~fab.parse.fortran.FortranParserWorkaround` objects, one for every file that can't be parsed.
Each object contains the symbol definitions and dependencies found in one source file.

.. code-block::

    config.steps = [
        ...
        Analyse(
            root_symbol='my_prog',
            special_measure_analysis_results=[
                FortranParserWorkaround(
                    fpath=Path(config.build_output / "path/to/file.f90"),
                    module_defs={'my_mod'}, symbol_defs={'my_func'},
                    module_deps={'other_mod'}, symbol_deps={'other_func'}),
            ])
        ...
    ]

Custom Step
^^^^^^^^^^^
An alternative approach for some problems is to write a custom step to modify the source so that the language
parser can process it. Here's a simple example, based on a
`real workaround <https://github.com/metomi/fab/blob/216e00253ede22bfbcc2ee9b2e490d8c40421e5d/run_configs/um/build_um.py#L268-L290>`_
where the parser gets confused by a variable called `NameListFile`.

.. code-block::

    class MyCustomCodeFixes(Step):
        def run(self, artefact_store, config):
            fpath = config.source_root / 'path/to/file.F90'
            in = open(fpath, "rt").read()
            out = in.replace("NameListFile", "MyRenamedVariable")
            open(fpath, "wt").write(out)

    config = BuildConfig(steps=[
        # grab steps first
        MyCustomCodeFixes()
        # FindSourceFiles, preprocess, etc, afterwards
    ])


Two-Stage Compilation
=====================
The :class:`~fab.steps.compile_fortran.CompileFortran` step compiles files in passes,
with each pass identifying all the files which can be compiled next, and compiling them with parallel processing.

Some projects have bottlenecks in their compile order, where lots of files are stuck behind a single file
which is slow to compile. Inspired by `Busby <https://www.osti.gov/biblio/1393322>`_, Fab can perform two-stage
compilation where all the modules are built first in *fast passes* using the `-fsyntax-only` flag,
and then all the slower object compilation can follow in a single pass.

The *potential* benefit is that the bottleneck is shortened, but there is a tradeoff with having to run through
all the files twice. Some compilers might not have this capability.

Two-stage compilation is configured with the `two_stage_flag` argument to the Fortran compiler.

.. code-block::

    CompileFortran(two_stage_flag=True)


Config Reuse
============
If you find you have many build configs with duplicated code, it would be prudent to consider refactoring out
the commonality into a shared module.

In Fab's `example run configs <https://github.com/metomi/fab/tree/master/run_configs>`_,
we have two build scripts to compile GCOM. Much of the config for these two scripts is identical.
We extracted the common steps into
`gcom_build_steps.py <https://github.com/metomi/fab/blob/master/run_configs/gcom/gcom_build_steps.py>`_
and used them in
`build_gcom_ar.py <https://github.com/metomi/fab/blob/master/run_configs/gcom/build_gcom_ar.py>`_
and
`build_gcom_so.py <https://github.com/metomi/fab/blob/master/run_configs/gcom/build_gcom_so.py>`_.


Separate grab and build scripts
===============================
If you are running many builds from the same source,
you may wish to grab your repo in a separate script and call it less frequently.
In this case your grab script might only contain a single step.
You could import your grab config to find out where it put the source.

.. code-block::
    :caption: my_grab.py

    def my_grab_config():
        return BuildConfig(
            project_label='my source',
            steps=[
                GrabFcm(src='my_repo')
            ],
        )

    if __name__ == '__main__':
        my_grab_config().run()


.. code-block::
    :caption: my_build.py
    :emphasize-lines: 7

    from my_grab import my_grab_config

    def my_config():
        config = BuildConfig(
            project_label='my build',
            steps=[
                GrabFolder(src=my_grab_config().source_root),
                ...
            ],
        )

        return config

    if __name__ == '__main__':
        my_build_config().run()


Housekeeping
============
Fab will remove old files from the prebuilds folder.
By default, it will remove all prebuild files that are not part of the current build.
If you add a :class:`~fab.steps.cleanup_prebuilds.CleanupPrebuilds` step, you can keep prebuild files for longer.
This may be useful, for example, if you often switch between two versions of your code and want to keep the prebuild
speed benefits when building both.


Shared prebuilds
================
You can copy the contents of someone else's prebuilds folder into your own.
Fab uses hashes to keep track of the correct prebuilt files, and will find and use them.
There's also a helper step called :class:`~fab.steps.grab.prebuild.GrabPreBuild` you can add to your configs.


Psykalite (Psyclone overrides)
==============================
If you need to override a PSyclone output file with a handcrafted version,
you can use the ``overrides_folder`` argument to the :class:`~fab.steps.psyclone.Psyclone` step.
This is just a normal folder containing source files.
The step will delete any files it creates if there's a matching filename in the overrides folder.
