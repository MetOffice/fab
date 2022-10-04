
Fab Overview
************

Use Fab to build your Fortran and C project using a series of *build steps*.

Fab can analyse your code to determine dependencies, including those between C and Fortran.
It can work out which files need to be compiled, in which order, to create an executable
and it can build all your source into a static or shared library.


Steps
=====

You provide fab with list of build steps.

.. image:: img/steps.svg
    :width: 75%
    :align: center
    :alt: Some simple steps

|
Fab provides some ready made, configurable steps for you to use, and it's easy to create your own.


.. _artefacts_overview:

Artefacts
=========

Steps can read and create named collections of :term:`Artefact`
in the :term:`Artefact Store`.


.. image:: img/steps_and_store2.svg
    :width: 100%
    :alt: Artefact containment hierarchy

Fab runs each step in order, passing in the :term:`Artefact Store` which contains all previous steps' output.

Example Config
==============

Build configs are written in Python. Fab is designed to minimise user input by
by providing sensible defaults::

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


In the snippet above we don't tell the compiler which files to compile.
By default it knows to use the build tree created by the preceding analysis step.

Multiprocessing
===============

Steps have access to multiprocessing methods.
The Step class includes a multiprocessing helper method called :meth:`~fab.steps.Step.run_mp` which steps can call
from their :meth:`~fab.steps.Step.run` method to process a collection of artefacts in parallel.

