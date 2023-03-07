
Development
***********
Information for developers.

Install from source
===================
An editable install lets you edit the code without needing to reinstall fab.

.. code-block:: console

    $ pip install -e <fab-folder>


You can install extra features by using [test], [docs] or [dev], as defined in setup.py.

.. code-block:: console

    $ pip install -e <fab-folder>[dev]



Version numbering
=================
We use a `PEP 440 compliant <https://peps.python.org/pep-0440/#examples-of-compliant-version-schemes>`_
semantic versioning, of the form ``{major}.{minor}.{patch}[{a|b|rc}N]``

* 0.9.5
* 1.0.0a1
* 1.0.0a2
* 1.0.0b1
* 1.0.0rc1
* 1.0.0
* 1.0.1
* 1.1.0a1

Dev versions are not for release and cover multiple commits.
* 1.0.dev0
* ...
* 1.0.0
* 1.0.dev1
* ...
* 1.0.1


Version bumping
===============
The version number needs to be updated in two places

* source/fab/__init_.py
* docs/source/conf.py

Consider adding a developers' tool like `BumpVer <https://pypi.org/project/bumpver>`_.

Source code Analysis
====================
See :mod:`~fab.steps.analyse` for a description of the analysis process.

The class hierarchy for analysis results can be seen below.
Classes which are involved in source tree analysis contain symbol definitions and dependencies,
and the file dependencies into which they are converted.

.. image:: img/analysis_results_hierarchy.svg
    :width: 95%
    :align: center
    :alt: Analysis results class hierarchy


Incremental & Prebuilds
=======================
See :term:`Incremental Build` and :term:`Prebuild` for definitions.

Prebuild artefacts are stored in a flat *_prebuild* folder underneath the *build_output* folder.
They include a checksum in their filename to distinguish between different builds of the same artefact.
All prebuild files are named: `<stem>.<hash>.<suffix>`, e.g: *my_mod.123.o*.

Checksums
---------
Fab inserts a checksum in the filenames of prebuild artefacts. This checksum is derived from
everything which should trigger a rebuild if changed. Before an artefact is created, Fab will
calculate the checksum and search for an existing artefact so it can avoid reprocessing the inputs.

Analysis results
----------------
Analysis results are stored in files with a *.an* suffix.
The checksum in the filename is solely the hash of the analysed source file.
Note: this can change with different preprocessor flags.

Fortran module files
--------------------
When creating an module file from a Fortran source file, the prebuild checksum is created from hashes of:

 - source file
 - compiler
 - compiler version

Fortran object files
--------------------
When creating a object file from a Fortran source file, the prebuild checksum is created from hashes of:

 - source file
 - compiler
 - compiler version
 - compiler flags
 - modules on which the source depends


Github Actions
==============

Testing a PR
------------
todo

Build these docs
----------------
todo

Build singularity image
-----------------------
todo
