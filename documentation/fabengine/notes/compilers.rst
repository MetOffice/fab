Supporting Compilers
####################

One of the principles the toy build system is based on is: It's not the build
system's job to know about your platform. As such it is directed which compiler
to use either by a command-line argument or the de facto environment variables:
``FC``, ``CC`` and ``CXX``.

If the compiler it is directed to use cannot be found then an error is thrown
and build ceases.

Compiler Arguments
==================

The arguments passed to a compiler can be split down into a few broad
categories. These are discussed next.

Arguments For Common Functionality
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are a number of features which all (or nearly all) compilers offer but
which are controlled using different arguments. A good example of this is
controling the directory to which a Fortran compilers stores module files.

Intel compilers use the ``-module`` argument while GNU compilers use `-J`.
nVidia uses ``-module`` as well.

Another example would be how to enable OpenMP support; Intel uses ``-qopenmp``
while GNU use ``-fopenmp``. Meanwhile nVidia use ``-mp``.

We might implement this as a class per compiler with these valus wired into
them. Alternatively we might persue a more data driven model where we have a
single compiler class which is initialised from a file listing each compilers
particular arguments.

Project Arguments
^^^^^^^^^^^^^^^^^

Some compiler arguments will be required by a project. This will not be the
case for most projects but we do have a few which, for historical reasons, are
always compiled with real variables promoted to double width.

More useful for this class of argument relates to optimisations which go
pathalogical for particular source files with particular compilers and
particular compiler versions. In these cases we would like to turn that
optimisation off.

This tells us that each project needs the ability to specify special cases
for each version of each compiler it hsa been tested with. The build system
will then choose the correct special case based on the compiler it has been
instructed to use.

User Argument Bundles
^^^^^^^^^^^^^^^^^^^^^

The final group of arguments are those which interest the user. These will
often described different levels of optimisation and debug support. However,
they could also relate to profiler use, for example.

These arguments are often bundled together to allow for, e.g. Only backtrace
preserving optimisations, debug symbols and run-time array-bound checking.

As noted at the top, we don't want to be in the business of holding these
user bundles in the build system. They are only of interest to a subset of
users and their platforms, they are just dead weight to other users and
represent a maintenance burden to project owners.

They do represent a real requirement though, so must be supporter.

The proposed solution are user generated files which may be given to the build
system on invocation. These will need to support per compiler, per version
arguments and may need to support per file, but that use case is yet to be
proven.

These files need not support multiple named bundles, this functionality can be
obtained by having multiple named files.

Propagating Arguments Down the Build Tree
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We will get to the point where we are no longer pouring all the source into a
bucket but, instead, calling on prerequisites to build themselves. Once there,
the compiler arguments will need to be communicated down the prerequisite tree.

There is no reason why prerequisites would have the same named bundles as the
project using them, so it cannot be done by name. Instead it will have to be
done via the resolved argument list.
