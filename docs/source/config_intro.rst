.. _Config Intro:


Introduction to Config
**********************

Use Fab to build your Fortran and C project using a series of *build steps*.

Here is an example of a build config. They are written in Python.
It provides some ready made, configurable steps for you to use, and it's easy to create your own.

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

Fab is designed to minimise user input by by providing sensible defaults.
Build steps can read and create named collections in the :term:`Artefact Store`.
For example, in the snippet above we don't tell the compiler which files to compile.
By default it knows to use the build tree created by the preceding step.

More details about steps can be found in the :ref:`guide to writing config<Writing Config>`.
