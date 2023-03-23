.. _Config Intro:


Introduction to Config
**********************

Use Fab to build your Fortran and C project using a series of *build steps* which
are written in Python.

Here is an example of a build configuration. It provides some ready made
configurable steps for you to use, and it's easy to create your own custom steps.

.. code-block::

    config = Config(
        project_label='my project',
        steps=[
            GrabFolder(src='~/my_repo'),
            FindSourceFiles(),
            fortran_preprocessor(),
            Analyse(root_symbol='my_program'),
            CompileFortran(),
            LinkExe(),
        ])

.. note::

    The ``root_symbol`` is the name of the Fortran PROGRAM you wish to build,
    or ``"main"`` if it's in C.

Fab is designed to minimise user input by by providing sensible defaults.
By default it knows to use the build tree created by the preceding step.
Build steps can read and create named collections in the :term:`Artefact Store`.
For example, in the snippet above we don't tell the compiler which files to compile.


More details about steps can be found in the :ref:`guide to writing config<Writing Config>`.
