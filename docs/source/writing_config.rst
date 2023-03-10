.. _Writing Config:


How to Write a Build Config
***************************
This page walks through the process of writing a build script.

Config File
===========
Here's a simple config without any steps.

.. code-block::
    :linenos:
    :caption: build_it.py

    #!/usr/bin/env python3

    from fab.build_config import BuildConfig

    config = BuildConfig(
        project_label='my project',
        steps=[]
    )

    config.run()

If we want to run the build script from the command line,
we give it executable permission with the command `chmod +x build_it.py`.
We also add the `shebang <https://en.wikipedia.org/wiki/Shebang_(Unix)>`_ directive on line 1,
telling our computer it's a Python script.

The rest of the code creates and runs a build config without any steps.
The project label is used to calculate where to put any output files (see :term:`Project Workspace`).


Source Code
===========
Let's tell Fab where our source code is.

We use the :class:`~fab.steps.find_source_files.FindSourceFiles` step for this.
We can point this step to a source folder, which is a valid way to use this step.
However, because Fab can sometimes create artefacts alongside the source :sup:`1`,
we usually copy the source into the project workspace first using a :mod:`~fab.steps.grab` step.

A grab step will copy files from a folder or remote repo into the project workspace, into a folder called "source".

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 4,5,10,11

    #!/usr/bin/env python3

    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import FindSourceFiles
    from fab.steps.grab import FcmExport

    config = BuildConfig(
        project_label='my project',
        steps=[
            GrabFolder(src='~/my_repo'),
            FindSourceFiles(),
        ]
    )

    config.run()

.. note::
    *Sensible defaults*

    Fab tries to minimise user input by providing *sensible defaults*.
    In this case, the user doesn't have to specify where the code goes.
    The grab and FindSourceFiles steps already know what to do by default.
    Sensible defaults can be overridden.

Please see the documentation for :class:`~fab.steps.find_source_files.FindSourceFiles` for more information,
including how to exclude certain source code from the build. More grab steps can be found in the :mod:`~fab.steps.grab`
module.

:sup:`1` See :class:`~fab.steps.c_pragma_injector.CPragmaInjector` for an example of a step which creates
artefacts in the source folder.



Preprocess
==========
Next we want to preprocess our source code.
Preprocessing resolves any `#include` and `#ifdef` directives in the code,
which must happen before we analyse it.

Thanks to Fab's sensible defaults, the Fortran preprocessor knows where to find the Fortran source code.
It was added to the :term:`Artefact Store` by the preceding step.

.. note::
    *Artefact Store*

    Steps generally create and find artefacts in this dictionary, arranged into named collections.
    The Fortran preprocessor automatically looks for Fortran source code in a collection named `'all_source'`,
    which is the default output from the preceding FindSourceFiles step.


.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 6,13

    #!/usr/bin/env python3

    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import FindSourceFiles
    from fab.steps.grab import FcmExport
    from fab.steps.preprocess import fortran_preprocessor

    config = BuildConfig(
        project_label='my project',
        steps=[
            GrabFolder(src='~/my_repo'),
            FindSourceFiles(),
            fortran_preprocessor(),
        ]
    )

    config.run()

Preprocessed files are created in the `'build_output'` folder, inside the project workspace.
See the docs for :func:`~fab.steps.preprocess.fortran_preprocessor` for more,
including how to pass flags to the command line tool.

Analyse
=======
We must :class:`~fab.steps.analyse.Analyse` the source code to determine the Fortran compile order.

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 3,15

    #!/usr/bin/env python3

    from fab.steps.analyse import Analyse
    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import FindSourceFiles
    from fab.steps.grab import FcmExport
    from fab.steps.preprocess import fortran_preprocessor

    config = BuildConfig(
        project_label='my project',
        steps=[
            GrabFolder(src='~/my_repo'),
            FindSourceFiles(),
            fortran_preprocessor(),
            Analyse(root_symbol='my_program'),
        ]
    )

    config.run()

We tell the analyser which `root_symbol` we want to build into an executable.
This argument is omitted when building a shared or static library.

Compile and Link
================
The :class:`~fab.steps.compile_fortran.CompileFortran` step creates module and object files
in the build output folder. The :class:`~fab.steps.link.LinkExe` step then creates the executable.

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 4,8,18,19

    #!/usr/bin/env python3

    from fab.steps.analyse import Analyse
    from fab.steps.compile_fortran import CompileFortran
    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import FindSourceFiles
    from fab.steps.grab import FcmExport
    from fab.steps.link import LinkExe
    from fab.steps.preprocess import fortran_preprocessor

    config = BuildConfig(
        project_label='my project',
        steps=[
            GrabFolder(src='~/my_repo'),
            FindSourceFiles(),
            fortran_preprocessor(),
            Analyse(root_symbol='my_program'),
            CompileFortran(),
            LinkExe(),
        ]
    )

    config.run()

The CompileFortran step uses *gfortran* by default,
and the LinkExe step uses *gcc* by default.
They can be configured to use other compilers.


Flags
=====
Preprocess, compile and link steps usually need configuration to specify command-line arguments
to the underlying tool, such as symbol definitions, include paths, optimisation flags, etc.

We can add flags to our linker step::

    flags=['-lm', '-lnetcdff', '-lnetcdf']

For preprocessing and compilation, we sometimes need to specify flags *per-file*.
These steps accept both common flags and *path specific* flags::

    common_flags=['-O2'],
    path_flags=[
        AddFlags('$output/um/*', ['-I' + '/gcom'])
    ],

This will add `-O2` to every invocation of the tool, but only add the */gcom* include path when processing
files in the *<project workspace>/build_output/um* folder.

.. note::
    This can require some understanding of where and when files are placed in the *build_output* folder:
    It will generally match the structure you've created in *<project workspace>/source*, with your grab steps.
    Early steps like preprocessors generally read files from *source* and write to *build_output*.
    Later steps like compilers generally read files which are already in *build_output*.

Path matching is done using Python's `fnmatch <https://docs.python.org/3.10/library/fnmatch.html#fnmatch.fnmatch>`_.
We can current only *add* flags for a path, using the :class:`~fab.build_config.AddFlags` class.
If demand arises, Fab developers may add classes to remove or modify flags by path - please let us know!


C Code
======
Fab comes with C processing steps.
The :func:`~fab.steps.preprocess.c_preprocessor` and :class:`~fab.steps.compile_c.CompileC` Steps
behave like their Fortran equivalents. However, there is also a preceding step called
the :class:`~fab.steps.c_pragma_injector.CPragmaInjector`.

.. note::
    Fab needs to inject pragmas into C code before it is preprocessed in order to know which dependencies
    are for user code, and which are for system code to be ignored.

The C pragma injector creates new C files with ".prag" file extensions, in the same folder as the original source.
The C preprocessor looks for the output of this step by default.
If not found, it will fall back to looking for .c files in the source listing.

.. code-block::

        steps = [
            ...
            CPragmaInjector(),
            c_preprocessor(),
            ...
        ]

The pragma injector may be merged into the preprocessor in the future,
and the *.prag* files may be created in the build_output instead of the source folder.


Further Reading
===============
More advanced config topics are discussed in :ref:`Advanced Config Topics`.

You can see more complicated configs in Fab's
`example run configs <https://github.com/metomi/fab/tree/master/run_configs>`_.
