How to Write a Build Config
===========================
You'll need a development environment with Fab installed (see :ref:`install`).


Config File
-----------
Not only is Fab written in Python, its build configs are too.
However, writing Fab config should feel as simple as writing traditional config.
The user isn't exposed to underlying details unless they need more control.

Here's a simple config without any build steps.

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

The rest of the code creates a build config without any steps in it.
The project label is used to calculate where to put any output files (see :term:`Project Workspace`).


Source Code
-----------
Let's tell Fab where our source code is.

We use the :class:`~fab.steps.find_source_files.FindSourceFiles` step for this.
We can point this step to our local repo, which is a valid way to use this step.
However, because Fab can sometimes create artefacts alongside the source :sup:`1`,
we usually copy the source into the project workspace first using a :mod:`~fab.steps.grab` step.

A grab step will copy files from a folder or repo into the project workspace, into a folder called "source".

Fab tries to minimise user input by having *sensible defaults*.
In this case, the user doesn't need to think about the source location inside the project workspace
because the grab steps and the FindSourceFiles step know the default location.

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 4,5,10,11

    #!/usr/bin/env python3

    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import FindSourceFiles
    from fab.steps.grab import GrabFcm

    config = BuildConfig(
        project_label='my project',
        steps=[
            GrabFolder(src='~/my_repo'),
            FindSourceFiles(),
        ]
    )

    config.run()


1) See :class:`~fab.steps.c_pragma_injector.CPragmaInjector` for an example of a step which creates
   artefacts in the source folder.



Preprocess
----------
Next we want to preprocess our source code.
Preprocessing resolves any `#include` and `#ifdef` directives in the code,
which must happen before we analyse it.

Thanks to Fab's sensible defaults, the Fortran preprocessor know where to find the Fortran source code,
which was added to the :term:`Artefact Store` by the previous step.

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 6,13

    #!/usr/bin/env python3

    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import FindSourceFiles
    from fab.steps.grab import GrabFcm
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

Preprocessed files are created in the "build_output" folder, inside the project workspace.
See the docs for :func:`~fab.steps.preprocess.fortran_preprocessor` for more,
including how to pass arguments to the command.

Analyse
-------
We need to know the order in which to compile our Fortran code, so we must first
:class:`~fab.steps.analyse.Analyse` it.

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 3,15

    #!/usr/bin/env python3

    from fab.steps.analyse import Analyse
    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import FindSourceFiles
    from fab.steps.grab import GrabFcm
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
----------------
The :class:`~fab.steps.compile_fortran.CompileFortran` step creates mod and object files
in the build output folder. The :class:`~fab.steps.link.LineExe` step then creates the executable.

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 4,8,18,19

    #!/usr/bin/env python3

    from fab.steps.analyse import Analyse
    from fab.steps.compile_fortran import CompileFortran
    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import FindSourceFiles
    from fab.steps.grab import GrabFcm
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
These can be configured to use other compilers.


Further Reading
---------------
More advanced config topics are discussed in :ref:`Advanced Config Topics`.

You can see more complicated configs in Fab's
`example run configs <https://github.com/metomi/fab/tree/master/run_configs>`_.
