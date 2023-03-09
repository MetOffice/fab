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

 * dependency analysis / compile order
 * extensible with arbitrary tools, e.g. PSYclone
 * incremental operation, process what's changed
 * zero-config capability

For more, please see the :ref:`features<Features>` page.

Running fab
===========
 * how to :ref:`set up an environment<Environment>`
 * how to :ref:`install fab<Install>`
 * intro to :ref:`config files<Config>`

See also
========
 * `Project wiki <https://github.com/metomi/fab/wiki>`_
 * `Fab on PyPI <https://pypi.org/project/sci-fab/>`_
 * `Fab on Github <https://github.com/metomi/fab>`_
 * :ref:`Developers guide<Development>`


.. toctree::
   :maxdepth: 2
   :caption: Contents:
   :hidden:

   install
   config
   advanced_config
   features
   Api Reference <apidoc/modules>
   development
   glossary
   genindex
   py-modindex
