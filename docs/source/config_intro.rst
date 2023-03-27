.. _Config Intro:


Introduction to Configuration
*****************************

Use Fab to build your Fortran and C project using a series of *build steps* which
are written in Python.

Here is an example of a build configuration. It provides some ready made
configurable steps for you to use, and it's easy to create your own custom steps.

.. code-block::

        with BuildConfig(project_label='<project label') as config:
            grab_folder(config, src='<path to source folder>')
            find_source_files(config)
            preprocess_fortran(config)
            analyse(config, root_symbol='<program>')
            compile_fortran(config)
            link_exe(config)

.. note::

    The ``root_symbol`` is the name of the Fortran PROGRAM you wish to build,
    or ``"main"`` if it's in C. You can ask Fab to discover and build everything
    with the :func:`find_programs<fab.steps.analyse.analyse>` flag instead.

Fab is designed to minimise user input by by providing sensible defaults.
By default it knows to use the build tree created by the preceding step.
Build steps can read and create named collections in the :term:`Artefact Store`.
For example, in the snippet above we don't tell the compiler which files to compile.


More details about steps can be found in the :ref:`guide to writing configuration<Writing Config>`.
