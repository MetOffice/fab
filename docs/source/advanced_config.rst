.. _Advanced Config Topics:

Advanced Config
***************


Custom Steps
============
If you need a custom build step, you can create a subclass of the :class:`~fab.steps.Step` class.

Fab includes some examples of a custom step. A simple example was created for building JULES.
The :class:`~fab.steps.root_inc_files.RootIncFiles` step copies all `.inc` files in the source tree
into the root of the source tree, to make subsequent preprocessing flags easier to configure.

That was a simple example that didn't need to interact with the :term:`Artefact Store`.
If you need to insert a custom step between two Fab steps, you may need your custom step to create
an :term:`Artefact Collection`, and to configure the subsequent step to use your new collection.
Many Fab steps have an optional `source` argument which overrides the default :term:`Artefacts Getter`.

.. code-block::

    class CustomStep(object):
        def run(self, artefact_store: Dict, config):
            artefact_store['custom_artefacts'] = do_something(artefact_store['step 1 artefacts'])


    config = BuildConfig('my_proj', steps=[
        FabStep1(),
        CustomStep(),
        FabStep2(source=CollectionGetter('custom_artefacts')),
    ])


Two-Stage Compilation
=====================
The :class:`~fab.steps.compile_fortran.CompileFortran` step compiles files in passes,
with each pass identifying all the files which can be compiled next, and compiling them with parallel processing.

Some projects have bottlenecks in their compile order, where lots of files are stuck behind a single file
which is slow to compile. Inspired by `Busby <https://www.osti.gov/biblio/1393322>`_, Fab can perform two-stage
compilation where all the modules are built first in *fast passes* using the `-fsyntax-only` flag,
and then all the slower object compilation can follow in a single pass.

The *potential* benefit is that the bottleneck is shortened, but there is a tradeoff with having to run through
all the files twice. Some compilers might not have this capability.

Two-stage compilation is configured with the `two_stage_flag` argument to the Fortran compiler.


Multiple Configs
================
If you find you have many build configs with duplicated code, it would be prudent to consider refactoring out
the commonality into a shared module.

.. note::

    Fab comes with some example build configs which we regularly use to build some Met Office projects
    and test Fab.

In Fab's `example run configs <https://github.com/metomi/fab/tree/master/run_configs>`_,
we have two build scripts to compile GCOM into a shared and static library.
Much of the config for these two scripts is identical,
with just a single compile flag and the final step being different.
We extracted the common steps into
`gcom_build_steps.py <https://github.com/metomi/fab/blob/master/run_configs/gcom/gcom_build_steps.py>`_
and used them in
`build_gcom_ar.py <https://github.com/metomi/fab/blob/master/run_configs/gcom/build_gcom_ar.py>`_
and
`build_gcom_so.py <https://github.com/metomi/fab/blob/master/run_configs/gcom/build_gcom_so.py>`_.
