Considering Incremental Building
################################

A common feature of build systems is known as an "incremental build." In this
mode of operation, only those source files which have been changed will be
compiled. Resulting artefacts from the previous build will be re-used for those
source files which have not changed.

This simple concept has one complicating factor, when a change to the source
changes the API of a component, everything which depends on that component
must also be rebuilt. Otherwise there will be a link failure due to mismatching
API implementation and calls to it.

The reason we pursue this concept is the greatly reduced build times it
represents. In a large code base, the number of source files which change
between compilations is small. As such, the saving from not having to compile
the majority of the source is considerable.

Determining Staleness
=====================

The heart of an incremental build system is a mechanism to determine if a
source file, or its dependencies, have changed since the most recent build.

By Timestamp
++++++++++++

For a long time this was done by checking the modification timestamp of the
files and comparing it with the timestamp of the resulting object file. If the
source is more recent then it has been edited since the previous build.

The problem with this approach is that time stamps can become modified through
processes such as an archive/extract cycle.

By Hash
+++++++

More recent systems have hashed the source file and compared that with the hash
from when it was last built. A difference in hash indicates a change in the
source and a trigger for a rebuild.

This approach works even through an archive/extract cycle and is much more
robust. The cost, however, is that an expensive hashing of the file is needed
instead of a cheap interrogation of the file metadata.

Modern computers are fast and hashing of this nature does not take long, the
cost comes in the file access. This is particularly true when the files are
hosted on a filesystem such as Luster, which does not handle frequent access to
small files well.

Comparing Solutions
+++++++++++++++++++

Ultimately incremental building is an aid to development, not a situation where
archive/extract cycles are expected. So although the hashing approach solves
a real problem it may be unnecessary for the circumstances, particularly given
its cost.

Added Complications
+++++++++++++++++++

Although the freshness of the source file has always been the triggering factor
for incremental building, there is another to consider.

Changing the arguments to the build tool also potentially change its resulting
files. An ideal build system would also track this.

The solution is a bit more clear cut in this instance. There is no quickly
accessed meta-data to consult and calculating a hash will be an entirely in
memory operation.

In light of this, it seems clear that hashing the tool arguments is the way to
detect change in them.

Met Office "Prebuilds"
======================

Incremental building provides substantial savings in time and a commensurate
tightening of the code-compile-test loop. However, it does require an initial
full build to prime the system with build artefacts. This takes exactly as long
as a full build always takes.

Traditionally, the concept of incremental building has been extended at the
Met Office with so-called "prebuilds." This is a way to avoid the cost of that
initial build by providing a canned set of build artefacts.

It was probably more important in the 90s when compilation was a lot slower but
it is a fairly straight-forward extension of the incremental build concept so
we aim to support it.

A prebuilds collection is something likely to experience archive/extract cycles
so interacting with them might benefit from the hash-based approach to
freshness determination.

Non-Standard Metadata
======================

The freshness information relates to a file but is not a standard property of
files on disc. At the moment, Fab adds the source file hash to the resulting
filenames.

Imagine a source file ``module.f90`` which generates the hash "123abc." The
resulting files become ``module.123abc.mod`` and ``module.123abc.o``.

To determine whether the source file needs to be recompiled, its hash is
calculated and the working directory tested to see if it contains files
``module.<hash>.mod`` and ``module.<hash>.o``.

This is a straight forward approach which we might continue. However, an
alternative is to implement a kind of virtual filesystem. This is not a pretend
disc provided by the operating system but, rather, a database which allows us
to manage all files of interest together.

Such a system can extend the metadata associated with a file in whatever way
we see fit.

Staleness Indicators
====================

Changes to any of the following should trigger a reprocessing of a source
file:

* Source file
* Source prerequiste files
* Prerequisite libraries (name and version)
* Tool name and version
* Tool arguments
* Build script
* Fab framework

We may decide that we don't care about all of these things, but they should be
considered and those deemed important part of the hash recorded against a file.

Implementation
==============

There are a number of considerations for implementation.

Staleness Detection
+++++++++++++++++++

This should likely be inherited in the abstract ``Action`` class and inherited
by all actions. Implementing staleness detection in every action is a recipe
for trouble and wasted effort.

Further more, the decision on whether to run the action should not be the
responsibility of the action, it should be managed by the work queue manager.

Split ``perform`` Method
++++++++++++++++++++++++

It is possible that action "perform" methods will need to be split into the
part which does the work and the part which raises subsequent actions. This
is because subsequent actions may still need to operate, there is just no need
to regenerate the current intermediate file.

Prerequisites May Be More Complicated
+++++++++++++++++++++++++++++++++++++

We may need to differentiate between prerequisites which are ready and stale,
compared to those which a ready and fresh.

Linkers Can Cause Problems
++++++++++++++++++++++++++

Link actions do not know, a priori, whether their prerequisites are stale or
fresh because they don't know the full extent of their prerequisites until the
dependency analysis is complete.

This problem is likely solved by delegating staleness determination to the
actions. Everything should then just fall out of the queue, as before.
