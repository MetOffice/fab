.. Fab documentation master file, created by
   sphinx-quickstart on Mon Jan 24 17:04:51 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Fab's documentation!
*******************************
Version |version| (release |release|).

What is fab?
============

An open source build system for Fortran and C projects.
Initially designed to build the Met Office's major scientific applications, LFRic and the UM.

Why use fab?
============
Fab can analyse your code to determine dependencies, including those between C and Fortran.
It can work out which files need to be compiled, in which order, to create an executable
or library. Features include:

 * automatically detects dependency hierarchy / compile order
 * works with code generation tools, e.g. PSYclone
 * automatic discovery of source files
 * zero-config capability
 * extensible with arbitrary tools
 * written in Python
 * smart incremental operation, only re-processing what has changed
 * git, svn and fcm capabilities

For more, please see the :ref:`Features` page.

Running fab
===========
 * how to :ref:`set up an environment<Environment>`
 * how to install fab
 * intro to config files

See also
========
 * Developers
 * Project wiki
 * Releases
 * Fab on Github




Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   overview
   install
   howto_write_config
   advanced_config
   features
   Api Reference <apidoc/modules>
   development
   glossary
   genindex
   modindex
