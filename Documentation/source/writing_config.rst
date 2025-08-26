.. _Writing Config:


How to Write a Build Configuration
**********************************

This page walks through the process of writing a build script.

Configuration File
==================

Here's a simple configuration without any steps.

.. code-block::
    :linenos:
    :caption: build_it

    #!/usr/bin/env python3
    from logging import getLogger

    from fab.build_config import BuildConfig

    logger = getLogger('fab')

    if __name__ == '__main__':

        with BuildConfig(project_label='<project label>') as state:
            pass

If we want to run the build script from the command line,
we give it executable permission with the command ``chmod +x build_it``.
We also add the `shebang <https://en.wikipedia.org/wiki/Shebang_(Unix)>`_ directive on line 1,
telling our computer it's a Python script.

Pick a project label. Fab creates a :term:`project workspace` with this name.


Source Code
===========

Let's tell Fab where our source code is.

We use the :func:`~fab.steps.find_source_files.find_source_files` step for this.
We can point this step to a source folder, however, because Fab can sometimes
create artefacts alongside the source [1]_, we usually copy the source into the
project workspace first using a :mod:`~fab.steps.grab` step.

A grab step will copy files from a folder or remote repo into a folder called
"source" within the project workspace.

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 5,6,13,14

    #!/usr/bin/env python3
    from logging import getLogger

    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import find_source_files
    from fab.steps.grab.folder import grab_folder

    logger = getLogger('fab')

    if __name__ == '__main__':

        with BuildConfig(project_label='<project label>') as state:
            grab_folder(state, src='<path to source folder>')
            find_source_files(state)


.. note::
    Fab tries to minimise user input by providing *sensible defaults*.
    In this case, the user doesn't have to specify where the code goes.
    The grab and find_source_files steps already know what to do by default.
    Sensible defaults can be overridden.

Please see the documentation for :func:`~fab.steps.find_source_files.find_source_files` for more information,
including how to exclude certain source code from the build. More grab steps can be found in the :mod:`~fab.steps.grab`
module.

After the find_source_files step, there will be a collection called ``"INITIAL_SOURCE"``, in the artefact store.

.. [1] See :func:`~fab.steps.c_pragma_injector.c_pragma_injector` for an example of a step which
    creates artefacts in the source folder.


Preprocess
==========

Next we want to preprocess our source code.
Preprocessing resolves any `#include` and `#ifdef` directives in the code,
which must happen before we analyse it.

Steps generally create and find artefacts in the :term:`Artefact Store`, arranged into named collections.
The :func:`~fab.steps.preprocess.preprocess_fortran`
automatically looks for Fortran source code in a collection named `'INITIAL_SOURCE'`,
which is the default output from the preceding :funcfind_source_files step.
It filters just the (uppercase) ``.F90`` files.

.. note::

    Uppercase ``.F90`` are preprocessed into lowercase ``.f90``.

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 7,16

    #!/usr/bin/env python3
    from logging import getLogger

    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import find_source_files
    from fab.steps.grab.folder import grab_folder
    from fab.steps.preprocess import preprocess_fortran

    logger = getLogger('fab')

    if __name__ == '__main__':

        with BuildConfig(project_label='<project label>') as state:
            grab_folder(state, src='<path to source folder>')
            find_source_files(state)
            preprocess_fortran(state)


Preprocessed files are created in the `'build_output'` folder, inside the project workspace.
After the fortran_preprocessor step, there will be a collection called ``"preprocessed_fortran"``, in the artefact store.


PSyclone
========

If you want to use PSyclone to do code transformation and pre-processing (see https://github.com/stfc/PSyclone),
you must run :func:`~fab.steps.psyclone.preprocess_x90` and :func:`~fab.steps.psyclone.psyclone`,
before you run the :func:`~fab.steps.analyse.analyse` step below.

* For :func:`~fab.steps.psyclone.preprocess_x90`:
            You can pass in `common_flags` list as an argument.
* For :func:`~fab.steps.psyclone.psyclone`:
            You can pass in:

            * kernel file roots to `kernel_roots`,
            * a function to get transformation script to `transformation_script`
              (see examples in ``~fab.run_configs.lfric.gungho.py`` and ``~fab.run_configs.lfric.atm.py``),
            * command-line arguments to `cli_args`,
            * override for input files to `source_getter`,
            * folders containing override files to `overrides_folder`.


.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 8,18,19

    #!/usr/bin/env python3
    from logging import getLogger

    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import find_source_files
    from fab.steps.grab.folder import grab_folder
    from fab.steps.preprocess import preprocess_fortran
    from fab.steps.psyclone import psyclone, preprocess_x90

    logger = getLogger('fab')

    if __name__ == '__main__':

        with BuildConfig(project_label='<project label>') as state:
            grab_folder(state, src='<path to source folder>')
            find_source_files(state)
            preprocess_fortran(state)
            preprocess_x90(state)
            psyclone(state)


After the psyclone step, two new source files will be created for each .x90 file in the `'build_output'` folder.
These two output files will be added under ``FORTRAN_BUILD_FILES`` collection to the artefact store.


.. _Analyse Overview:

Analyse
=======

We must :func:`~fab.steps.analyse.analyse` the source code to determine which
Fortran files to compile, and in which order.

The Analyse step looks for source to analyse in two collections:

* ``FORTRAN_BUILD_FILES``, which contains all ``.f90`` found in the source, all ``.F90`` files we pre-processed into ``.f90``, and files created by any additional step (e.g. PSyclone).
* ``C_BUILD_FILES``, all preprocessed c files.

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 4,21

    #!/usr/bin/env python3
    from logging import getLogger

    from fab.steps.analyse import analyse
    from fab.build_config import BuildConfig
    from fab.steps.find_source_files import find_source_files
    from fab.steps.grab.folder import grab_folder
    from fab.steps.preprocess import preprocess_fortran
    from fab.steps.psyclone import psyclone, preprocess_x90

    logger = getLogger('fab')

    if __name__ == '__main__':

        with BuildConfig(project_label='<project label>') as state:
            grab_folder(state, src='<path to source folder>')
            find_source_files(state)
            preprocess_fortran(state)
            preprocess_x90(state)
            psyclone(state)
            analyse(state, root_symbol='<program>')


Here we tell the analyser which :term:`Root Symbol` we want to build into an executable.
Alternatively, we can use the ``find_programs`` flag for Fab to discover and build all programs.

After the Analyse step, there will be a collection called ``BUILD_TREES``, in the artefact store.


Compile and Link
================

The :func:`~fab.steps.compile_fortran.compile_fortran` step compiles files in
the ``BUILD_TREES`` collection. The :func:`~fab.steps.link.link_exe` step
then creates the executable.

.. code-block::
    :linenos:
    :caption: build_it.py
    :emphasize-lines: 6,9,24,25

    #!/usr/bin/env python3
    from logging import getLogger

    from fab.steps.analyse import analyse
    from fab.build_config import BuildConfig
    from fab.steps.compile_fortran import compile_fortran
    from fab.steps.find_source_files import find_source_files
    from fab.steps.grab.folder import grab_folder
    from fab.steps.link import link_exe
    from fab.steps.preprocess import preprocess_fortran
    from fab.steps.psyclone import psyclone, preprocess_x90

    logger = getLogger('fab')

    if __name__ == '__main__':

        with BuildConfig(project_label='<project label>') as state:
            grab_folder(state, src='<path to source folder>')
            find_source_files(state)
            preprocess_fortran(state)
            preprocess_x90(state)
            psyclone(state)
            analyse(state, root_symbol='<program>')
            compile_fortran(state)
            link_exe(state)


After the :func:`~fab.steps.link.link_exe` step, the executable name can be found in a collection called ``EXECUTABLES``.

ArtefactStore
=============
Each build configuration contains an artefact store, containing various
sets of artefacts. The artefact sets used by Fab are defined in the
enum :class:`~fab.artefacts.ArtefactSet`. The most important sets are ``FORTRAN_BUILD_FILES``,
``C_BUILD_FILES``, which will always contain all known source files that
will need to be analysed for dependencies, compiled, and linked. All existing
steps in Fab will make sure to maintain these artefact sets consistently,
for example, if a ``.F90`` file is preprocessed, the ``.F90`` file in
``FORTRAN_BUILD_FILES`` will be replaced with the corresponding preprocessed
``.f90`` file. Similarly, new files (for examples created by PSyclone)
will be added to ``FORTRAN_BUILD_FILES``. A user script can adds its own
artefacts using strings as keys if required.

The exact flow of artefact sets is as follows. Note that any artefact
sets mentioned here can typically be overwritten by the user, but then
it is the user's responsibility to maintain the default artefact sets
(or change them all):

..
  My apologies for the LONG lines, they were the only way I could find
  to have properly indented paragraphs :(

1. :func:`~fab.steps.find_source_files.find_source_files` will add all source files it finds to ``INITIAL_SOURCE`` (by default, can be overwritten by the user). Any ``.F90`` and ``.f90`` file will also be added to ``FORTRAN_BUILD_FILES``, any ``.c`` file to ``C_BUILD_FILES``, and any ``.x90`` or ``.X90`` file to ``X90_BUILD_FILES``. It can be called several times if files from different root directories need to be added, and it will automatically update the ``*_BUILD_FILES`` sets.
2. Any user script that creates new files can add files to ``INITIAL_SOURCE`` if required, but also to the corresponding ``*_BUILD_FILES``. This will happen automatically if :func:`~fab.steps.find_source_files.find_source_files` is called to add these newly created files.
3. If :func:`~fab.steps.c_pragma_injector.c_pragma_injector` is being called, it will handle all files in ``C_BUILD_FILES``, and will replace all the original C files with the newly created ones. For backward compatibility it will also store the new objects in the ``PRAGMAD_C`` set.
4. If :func:`~fab.steps.preprocess.preprocess_c` is called, it will preprocess all files in ``C_BUILD_FILES`` (at this stage typically preprocess the files in the original source folder, writing the output files to the build folder), and update that artefact set accordingly. For backward compatibility it will also store the preprocessed files in ``PREPROCESSED_C``.
5. If :func:`~fab.steps.preprocess.preprocess_fortran` is called, it will preprocess all files in ``FORTRAN_BUILD_FILES`` that end on ``.F90``, creating new ``.f90`` files in the build folder. These files will be added to ``PREPROCESSED_FORTRAN``. Then the original ``.F90`` are removed from ``FORTRAN_BUILD_FILES``, and the new preprocessed files (which are in ``PREPROCESSED_FORTRAN``) will be added. Then any ``.f90`` files that are not already in the build folder (an example of this are files created by a user script) are copied from the original source folder into the build folder, and ``FORTRAN_BUILD_FILES`` is updated to use the files in the new location.
6. If :func:`~fab.steps.psyclone.preprocess_x90` is called, it will similarly preprocess all ``.X90`` files in ``X90_BUILD_FILES``, creating the output files in the build folder, and replacing the files in ``X90_BUILD_FILES``.
7. If :func:`~fab.steps.psyclone.psyclone` is called, it will process all files in ``X90_BUILD_FILES`` and add any newly created file to ``FORTRAN_BUILD_FILES``, and removing them from ``X90_BUILD_FILES``.
8. The :func:`~fab.steps.analyse.analyse` step analyses all files in ``FORTRAN_BUILD_FILES`` and ``C_BUILD_FILES``, and add all dependencies to ``BUILD_TREES``.
9. The :func:`~fab.steps.compile_c.compile_c` and :func:`~fab.steps.compile_fortran.compile_fortran` steps will compile all files from ``C_BUILD_FILES`` and ``FORTRAN_BUILD_FILES``, and add them to ``OBJECT_FILES``.
10. If :func:`~fab.steps.archive_objects.archive_objects` is called, it will create libraries based on ``OBJECT_FILES``, adding the libraries to ``OBJECT_ARCHIVES``.
11. If :func:`~fab.steps.link.link_exe` is called, it will either use ``OBJECT_ARCHIVES``, or if this is empty, use ``OBJECT_FILES``, create the binaries, and add them to ``EXECUTABLES``.


Flags
=====

Preprocess, compile and link steps usually need configuration to specify
command-line arguments to the underlying tool, such as symbol definitions,
include paths, optimisation flags, etc. See also
:ref:`Advanced Flags<Advanced Flags>`.


C Code
======
Fab comes with C processing steps.
The :func:`~fab.steps.preprocess.preprocess_c` and :func:`~fab.steps.compile_c.compile_c` Steps
behave like their Fortran equivalents.

However preprocessing C currently requires a preceding step called the
:func:`~fab.steps.c_pragma_injector.c_pragma_injector`. This injects markers
into the C code so Fab is able to deduce which inclusions are user code and
which are system code. This allows system dependencies to be ignored.

See also :ref:`Advanced C Code<C Pragma Injector>`


Further Reading
===============

More advanced configuration topics are discussed in
:ref:`Advanced Config`.

You can see more complicated configurations in the
`developer testing directory <https://github.com/MetOffice/fab/tree/main/run_configs>`_.
