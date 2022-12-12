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
Sometimes, inserting a custom step means inserting a new :term:`Artefact Collection` into the flow of data between
steps. We can tell a subsequent step to read our new artefacts, instead of using it's default :term:`Artefacts Getter`.
We do this using the `source` argument, which most Fab steps accept.

.. code-block::

    class CustomStep(object):
        def run(self, artefact_store: Dict, config):
            artefact_store['custom_artefacts'] = do_something(artefact_store['step 1 artefacts'])


    config = BuildConfig('my_proj', steps=[
        FabStep1(),
        CustomStep(),
        FabStep2(source=CollectionGetter('custom_artefacts')),
    ])


Parser Workarounds
==================

Unrecognised Dependencies
-------------------------
If a language parser is not able to recognise a dependency within a file,
then Fab won't know the dependency needs to be compiled.
For example, some versions of fparser don't recognise a call on a one-line if statement.
In this case we can manually add the dependency using the `unreferenced_deps` argument to
:class:`~fab.steps.analyse.Analyse`.

Pass in the name of the called function.
Fab will find the file containing this symbol and add it to the build.

.. code-block::
    :linenos:
    :emphasize-lines: 3

    config.steps = [
        ...
        Analyse(root_symbol='my_prog', unreferenced_deps=['my_func'])
        ...
    ]

Unparsable Files
----------------
If a language parser is not able to process a file at all,
then Fab won't know about any of its symbols and dependencies.
This can sometimes happen to *correct code* which compilers *are* able to process,
for example if the language parser is still maturing and can't yet handle an unusual syntax.
In this case we can manually give Fab the analysis results it should have got from the parser
using the `special_measure_analysis_results` argument to :class:`~fab.steps.analyse.Analyse`.

Pass in a list of :class:`~fab.dep_tree.ParserWorkaround` objects, one for every file that can't be parsed.
Each object contains the symbol definitions and dependencies found in one source file.

.. code-block::
    :emphasize-lines: 3-10

    config.steps = [
        ...
        Analyse(
            root_symbol='my_prog',
            special_measure_analysis_results=[
                ParserWorkaround(
                    fpath=Path(config.build_output / "casim/lookup.f90"),
                    module_defs={'my_mod'}, symbol_defs={'my_func'},
                    module_deps={'other_mod'}, symbol_deps={'other_func'}),
            ])
        ...
    ]

Custom Step
^^^^^^^^^^^
An alternative approach for some problems is to write a custom step to modify the source so that the language
parser can process it. Here's a simple example, based on a
`real workaround <https://github.com/metomi/fab/blob/216e00253ede22bfbcc2ee9b2e490d8c40421e5d/run_configs/um/build_um.py#L268-L290>`_
we use to build the UM. The parser gets confused by a variable called `NameListFile`. Our config copies the source
into it's project folder first, so this step doesn't modify the developer's working code.

.. code-block::

    class MyCustomCodeFixes(Step):
        def run(self, artefact_store, config):
            fpath = config.source_root / 'um/control/top_level/um_config.F90'
            in = open(fpath, "rt").read()
            out = in.replace("NameListFile", "MyRenamedVariable")
            open(fpath, "wt").write(out)

    config = BuildConfig(steps=[
        # grab steps first
        MyCustomCodeFixes()
        # FindSourceFiles, preprocess, etc, afterwards
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


Separate Grabs
==============
If you are building many versions of a project from the same source,
you may wish to grab from your repo in a separate script.
In this case your grab script might only contain a single step.
You could import your grab config to find out where it put the source.

.. code-block::
    :caption: my_grab.py

    #!/usr/bin/env python3

    from fab.build_config import BuildConfig
    from fab.steps.grab import GrabFcm

    def my_grab_config(revision):
        return BuildConfig(
            project_label=f'my source {revision}',
            steps=[GrabFcm(src=my_repo, revision=revision)],
        )


    if __name__ == '__main__':
        my_grab_config(revision='v1.0').run()


.. code-block::
    :caption: my_build.py
    :emphasize-lines: 18

    #!/usr/bin/env python3

    from fab.steps.analyse import Analyse
    from fab.steps.compile_fortran import CompileFortran
    from fab.steps.find_source_files import FindSourceFiles
    from fab.steps.grab import GrabFolder
    from fab.steps.link import LinkExe
    from fab.steps.preprocess import fortran_preprocessor

    from my_grab import my_grab_config

    def my_ar_config(revision, compiler=None):
        compiler, _ = get_fortran_compiler(compiler)

        config = BuildConfig(
            project_label=f'my build {revision} {compiler}',
            steps=[
                GrabFolder(src=my_grab_config(revision=revision).source_root),
                FindSourceFiles(),
                fortran_preprocessor(),
                Analyse(),
                CompileFortran(),
                LinkExe(),
            ],
        )

        return config

    if __name__ == '__main__':
        my_build_config(revision='v1.0').run()
