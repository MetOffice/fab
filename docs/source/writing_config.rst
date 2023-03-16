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
        project_label='<project label>',
        steps=[]
    )

    config.run()

If we want to run the build script from the command line,
we give it executable permission with the command `chmod +x build_it.py`.
We also add the `shebang <https://en.wikipedia.org/wiki/Shebang_(Unix)>`_ directive on line 1,
telling our computer it's a Python script.

Pick a project label. Fab creates a project workspace with this name (see :term:`Project Workspace`).


Source Code
===========
Let's tell Fab where our source code is.

We use the :class:`~fab.steps.find_source_files.FindSourceFiles` step for this.
We can point this step to a source folder, which is a valid way to use this step.
However, because Fab can sometimes create artefacts alongside the source [1]_,
we usually copy the source into the project workspace first using a :mod:`~fab.steps.grab` step.

A grab step will copy files from a folder or remote repo into into a folder called "source" within the project workspace.

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 4,5,10,11

    #!/usr/bin/env python3

    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import FindSourceFiles
    from fab.steps.grab import FcmExport

    config = BuildConfig(
        project_label='<project label>',
        steps=[
            GrabFolder(src='<program name>'),
            FindSourceFiles(),
        ]
    )

    config.run()

.. note::
    Fab tries to minimise user input by providing *sensible defaults*.
    In this case, the user doesn't have to specify where the code goes.
    The grab and FindSourceFiles steps already know what to do by default.
    Sensible defaults can be overridden.

Please see the documentation for :class:`~fab.steps.find_source_files.FindSourceFiles` for more information,
including how to exclude certain source code from the build. More grab steps can be found in the :mod:`~fab.steps.grab`
module.

After the FindSourceFiles step, there will be a collection called ``"all_source"``, in the artefact store.

.. [1] See :class:`~fab.steps.c_pragma_injector.CPragmaInjector` for an example of a step which creates artefacts in the source folder.


Preprocess
==========
Next we want to preprocess our source code.
Preprocessing resolves any `#include` and `#ifdef` directives in the code,
which must happen before we analyse it.

Steps generally create and find artefacts in the :term:`Artefact Store`, arranged into named collections.
The :func:`~fab.steps.preprocess.fortran_preprocessor`
automatically looks for Fortran source code in a collection named `'all_source'`,
which is the default output from the preceding FindSourceFiles step.
It filters just the (uppercase) ``.F90`` files.

.. note::

    Uppercase ``.F90`` are preprocessed into lowercase ``.f90``.

The Fortran preprocessor will read the ``FPP`` environment variable to determine which tool to call.


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
        project_label='<project label>',
        steps=[
            GrabFolder(src='<program name>'),
            FindSourceFiles(),
            fortran_preprocessor(),
        ]
    )

    config.run()

Preprocessed files are created in the `'build_output'` folder, inside the project workspace.
After the fortran_preprocessor step, there will be a collection called ``"preprocessed_fortran"``, in the artefact store.


Analyse
=======
We must :class:`~fab.steps.analyse.Analyse` the source code to determine which Fortran files to compile,
and in which order.

The Analyse step looks for source to analyse in several collections:

 * ``.f90`` found in the source
 * ``.F90`` we pre-processed into ``.f90``
 * preprocessed c

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
        project_label='<project label>',
        steps=[
            GrabFolder(src='<program name>'),
            FindSourceFiles(),
            fortran_preprocessor(),
            Analyse(root_symbol='<program>'),
        ]
    )

    config.run()

We tell the analyser which `root_symbol` we want to build into an executable.

After the Analyse step, there will be a collection called ``"build_trees"``, in the artefact store.


Compile and Link
================
The :class:`~fab.steps.compile_fortran.CompileFortran` step compiles files in the ``"build_trees"`` collection.
The :class:`~fab.steps.link.LinkExe` step then creates the executable.

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
        project_label='<project label>',
        steps=[
            GrabFolder(src='<path to source folder>'),
            FindSourceFiles(),
            fortran_preprocessor(),
            Analyse(root_symbol='<program>'),
            CompileFortran(),
            LinkExe(),
        ]
    )

    config.run()

After the LinkeExe step, the executable name can be found in a collection called ``"executables"``.


Flags
=====
Preprocess, compile and link steps usually need configuration to specify command-line arguments
to the underlying tool, such as symbol definitions, include paths, optimisation flags, etc.
See also :ref:`Advanced Flags<Advanced Flags>`.


C Code
======
Fab comes with C processing steps.
The :func:`~fab.steps.preprocess.c_preprocessor` and :class:`~fab.steps.compile_c.CompileC` Steps
behave like their Fortran equivalents.

However, it currently requires a preceding step called the :class:`~fab.steps.c_pragma_injector.CPragmaInjector`.
Fab needs to inject pragmas into C code before it is preprocessed in order to know which dependencies
are for user code, and which are for system code to be ignored.

See also :ref:`Advanced C Code<Advanced C Code>`


Further Reading
===============
More advanced config topics are discussed in :ref:`Advanced Config`.

You can see more complicated configs in Fab's
`example run configs <https://github.com/metomi/fab/tree/master/run_configs>`_.
