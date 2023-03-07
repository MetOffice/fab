This page describes the environments in which Fab can be run.


Requirements
************
Fab has system dependencies and Python dependencies.


System Dependencies
===================
The minimum system requirements for Fab to build a project are:
 * Python >= 3.7
 * Fortran compiler
 * Linker (or archiver, if building libraries)

If your project includes C code:
 * libclang
 * python-clang


Environment definitions
-----------------------
Fab comes with some definition files which can be used to create a runtime environment for running Fab.

conda

docker

singularity

met office
build without modules


Installing Fab
==============
When you `pip install` Fab, the minimum Python dependencies (e.g. fparser) will also be installed automatically.

.. code-block:: console

    $ pip install sci-fab


Extra features
--------------
You can install some extra Python packages to enable more features.
This will install matplotlib for producing metrics graphs after a run, and psyclone for building LFRic.

.. code-block:: console

    $ pip install sci-fab[features]

See also Developers Installation
