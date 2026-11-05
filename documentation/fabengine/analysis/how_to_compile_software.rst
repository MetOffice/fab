How to Compile Software
=======================

In order to compile software to the point of a useful executable or library a
number of steps must be undertaken. These steps are detailed here.

A Full Build
++++++++++++

* Source processors are used:

  * Language preprocessor, e.g. ``fpp`` or ``cpp``.
  * ``Templaterator`` is used to generate source from templates.
  * ``Configurator`` is used to generate source from configuration metadata.
  * ``PSyclone`` is used to generate source:

    * Structured mode using the PSyKAl model.
    * Unstructured mode using source transmutation.
    * There is an ordering issue here as modules used by algorithms (in either
      mode) must be preprocessed before ``PSyclone`` tries to use them.

  * ``pFUnit`` is used to generate source for unit tests.
  * A processor may be used in more than one context.  e.g. a Fortran
    preprocessor is used on application source and on pFUnit generated test
    source.
  * Source processors are applied in sequence. The order depends on the
    underlying requirement for the build. For example, the generation of source
    from templates should take place before ``PSyclone`` is run.

* Original and processed source is analysed for dependencies according to the
  nature of the source.
* Necessary source files are processed to targets such as object files or new
  source files.

  * Compilers take source and create objects and possibly module files.
  * Packagers take objects to create libraries.
  * Linkers take objects and libraries to create executables.

* Libraries are packaged.

  * Dynamic linking libraries.
  * Object archives.

* Objects and libraries are linked to executables.

Responding to Test Failure
--------------------------

Test executables may be run as they become available. Failure may lead to
immediate termination of the build or it may just be noted for later.

Which is useful depends on the developer and the type of development they are
engaged with. Immediate termination gives quicker feedback of problems and
tightens the development/testing loop.

Delayed termination may give a broader overview of what is failing and how much
of the project will build. This slackens the development/testing loop but may
provide better system knowledge.

Incremental Building
--------------------

Previously processed targets can be used where their inputs, source and
configuration, are unchanged. This means only where source has changed (or
the configuration which controls the building of it) will it be rebuilt.

This reduces redundant work, thus speeding the rebuild process.

There is a special case of incremental building often referred to as
"prebuilds." This is a canned set of build artefacts for a particular
configuration of source, compiler and arguments.

A "Prebuild" is a special case of incremental build in which the initial build
is provided, meaning it is unnecessary to perform a "whole source tree" build
up front.

Change Detection
................

One of the first build tool frameworks, "Make", uses filestamps to detect
changes in prerequisites. If the source file is newer (has been modified more
recently than) the resulting object file, then it has changed and must be
recompiled.

There is a clear problem with this in that anything which changes filestamps
will upset this "newness" detection algorithm. Such events include archiving
and extracting the source or otherwise copying it between machines.

In these cases timestamps will often be reset to the time of the copy event.
This can cause mass recompilation of files which have not changed or failure to
recompile files which have.

In light of these shortcomings modern build systems often hash the contents of
the file and use a change in hash to detect change. Although the possibility of
hash collisions (where two different files produce the same hash) exists it is
extremely unlikely, particularly when comparing variants of the same file.

The downside of this hash based approach is that in order to know the hash of a
file every byte of it must be visited in order to compute the hash. In other
words, the file must be read in order to know if it has changed.

By comparison the "last modified" timestamp is metadata of the file and may be
obtained without reading the file.

Further more, incremental builds are something which exists to speed
development. Something which never usually involves migrating the source
between machines or other operations which would disrupt timestamps.

What this boils down to is that even though hashing the files is the
technically superior option, functionally it may be preferable to use
timestamps.

Two Pass Building of Fortran
++++++++++++++++++++++++++++

The need for module information when "using" other modules means compiling
Fortran is order sensitive. A module can't be used before it is compiled. This
contrasts with traditional C where header files are written by the developer
and are considered part of the source, meaning source can be compiled in any
order because the headers already exist.

This ordering of the build can be an issue because compiling, and specifically
optimising, a source file can take a long time. This means anything which has
that file as a prerequisite is left waiting for it to complete before it can
be compiled.

However, module files do not contain the results of compilation (and
optimisation). They hold only simple API information which is quick to extract
from the source.

Some Fortran compilers take advantage of this by offering the option to build
module files only. i.e. the object file is not built.

This is still order dependent but is much faster and only ever :math:`O(n)`
complexity. Once all the module files have been created slow compilation and
its (potentially) :math:`O(n^2)` complexity may occur in any order.

This offers a potential route to much faster builds by reducing choke points
in the DAG. It may also become relevant to C++ which recently gained a module
system similar to Fortran's.
