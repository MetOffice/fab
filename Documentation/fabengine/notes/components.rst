Project Components
##################

The classic approach to building scientific software is the "big bucket." In
this model, all the source is poured into a single, large bucket. It is then
stirred around with a stick until an executable floats to the top.

We would like to move to a different, component based, model. In this approach
the application is built from components which might, in turn, be built of
further components. Each component is responsible for building itself and
returning a library or object archive to the build which requested it. There
are both conceptual and practical advantages to this transition.

By separating the building of components it much more strongly enforces the
API between components. It's much harder to get away with just using bits of
a components internal gubbins. It also works against reverse dependencies where
a prerequisite makes use of the requisites internal gubbins.

These features will improve the software engineering of our code base but it
will also make each of the components much more usable on their own. This
should allow them to be reused by unrelated projects.

It also offers the potential of better build performance. If a component has
not changed since the last build there is no need to consider it. Like
incremental building but on a component level rather than a source file level.

Dependency Tree
===============

Currently all prerequisites are listed in the top level ``Makefile`` and must
be ordered correctly. A component must appear before any which make use of it.

This requires much more system knowledge than is ideal.

A better approach would be for each component to know its immediate
prerequisites and leave any further prerequisites to those components.

Accommodation In the Work Queue
===============================

The naive approach might be to have a separate work queue for each component.
This would work but would also imply communication between work
queues, which might be complicated.

Instead, it should be possible to make all this work on a single work queue.

A work queue is dependent on its prerequisite libraries, each of which is the
terminal of its own DAG [#dag]_. As such, source of a component has, as its
prerequisites, any libraries it depends on. This might be finessed to only
depend on relevant libraries if there were a way to work out which symbols
come from which libraries, before those libraries are compiled.

.. [#dag] Directed Acyclic Graph

Compiler Arguments
==================

As noted in :ref:`build-tree-arguments`, there should be no requirement for
components to name their compiler argument profiles similarly. As such, it is
the responsibility of the top level component (the application) to specify the
compiler arguments and pass that list to any prerequisites.

There will still be a need for components to modify this incoming list based
on local requirements, e.g. to turn off certain optimisations for certain
files.

Specification
=============

Each component will manage itself through its ``Fabfile``. Any prerequisites
will be specified in that file by URL, revision and path.

.. topic:: Illustrative Suggestion

   .. code-block:: python

      Component(
          "ssh://git@github.com/ExampleOrganisation/example.git",
          0x8f6a961139f810cc6c548d5b1200eb0ea5e7c996,
          "libraries/special"
      )

   In this example a component called "special" is found in the "example"
   repository. The path given must contain a ``Fabfile`` or the build script
   might be specified explicitly.

   There are potential optimisations to be made when several components come
   from the same repository. It may only be necessary to go to the network
   once, with subsequent components being created as worktrees, rather than
   clones. Or maybe the specific source can be extracted without the need to
   clone.
