User Stories
============

In order to better understand our requirements the following user stories have
been created.

Each consists of a scenario, the associated command line session, where
appropriate, and the expected outcome. They have been given names which
summarise the scenario.

They are intended to illustrate what we want the user experience of using our
build system to be.

Build Toy Code
++++++++++++++

The user has some source they have thrown together to test some idea. They want
to build it with the minimum of fuss.

.. code-block:: sh

   export FC=flang
   cd ~/toys/special
   fab

No ``Fabfile`` is found so "zero configuration" mode is enabled.

All ``.[Ff]90`` and ``.c(c|xx)?`` files are located below the currently
selected directory. These are analysed and all ``program`` units and
``int main(int argv, char *argc[])`` functions are discovered. Executables are
then build for each one. If none are found, a shared library or object archive
is built.

The compiler is determined from the command line or, if it is unspecified, the
``FC`` and ``C(C|XX)?`` environment variables. If neither offer up the goods
then there is nowhere else to go and an error message explaining what has gone
wrong and how to remedy it is produced.

Configured Build
++++++++++++++++

The user's source is too elaborate for "zero configuration" mode so they must
use "some configuration" mode.

.. code-block:: sh

   cd application/gungho_model
   fab -compiler nagfor

A file ``applications/gungho_model/FabFile`` is found and used to configure
the build. It contains dependencies on
``ssh://git@github.com/lfric_core/infrastructure@123abc`` and
``../../science/gungho``.

The infrastructure component is exported from version control. A ``FabFile`` is
discovered therein so execution passes to it. This results in an object archive
or shared library compiled using the same optimisation arguments except where
these are overridden by the library.

Execution then returns to the original build script before passing on to the
Gungho science library. This also depends on the infrastructure but it has
already been built so nothing further needs to be done. Instead the science
library is built, again as an object archive or shared library.

Once complete there are no further prerequisites so the application is built
and linked with the previously built libraries.

Build That Thing Over There
+++++++++++++++++++++++++++

The source is not in the currently selected directory.

.. code-block:: sh

   fab components/science

The specified directory is found to contain a ``FabFile`` so it is used to
configure the build. In particular it specifies ``../../infrastructure`` as
a prerequisite.

Control is passed to ``../../infrastructure/FabFile`` to build the library
before returning to complete the science component build.

As the science component is a library itself it contains no program entry
points so executables cannot be built. It does contain unit tests, however, so
these are built and run.

Use a 3rd Party Library
+++++++++++++++++++++++

In order to avoid re-inventing the wheel, the user wants to make use of the
YAXT and NetCDF libraries. Unfortunately the NetCDF installation on the user's
system is broken and can't be discovered in the normal way.

.. code-block:: sh

   cd applications/gungho-model
   fab

In this scenario the ``FabFile`` records the dependencies on YAXT and
``netcdff``. The build system uses ``pkg-config`` to discover a number of
things about YAXT. In normal circumstance it would also find out about
``netcdff`` as well. This would reveal that it further depends on ``netcdf``,
which would causes a second use of ``pkg-config`` to find out about ``netcdf``.

In this case, although information is available, it is wrong. An override is
needed. This could be the long standing ``FFLAGS`` and ``LDFLAGS`` environment
variables but in the case of NetCDF there is a ``nc-config`` tool which is a
single use equivalent to ``pkg-config``.

The details harvested in this way allow the compiler to be pointed at Fortran
modules and C(++) headers. It also allows the linker to be pointed towards the
shared library or object archive files.

Developing a New Feature
++++++++++++++++++++++++

The user is developing a new feature so needs rapid feedback on failures.

In general, when unit tests are able to be built they are, then they are run.

In this scenario the user probably wants to be alerted the moment a test fails
and the build terminated. This allows them to fix the problem and try again
giving a tight development loop.

Porting To a New Platform
+++++++++++++++++++++++++

The user is porting the code to a new machine. They need a broad overview of
problems.

In general, when unit tests are able to be built they are, then they are run.

In this scenario the user probably wants the build to go as far as it can with
any test failures recorded for later inspection. Only when everything which can
be built has been should the build terminate and present the list of failing
tests.

This gives a wider scope view of the problems in the code base.

Controlling the Compiler
++++++++++++++++++++++++

The user needs different sets of compiler arguments to control optimisation and
debug symbols depending on whether they are developing a new feature or
building for production. There is also the orthogonal issue of whether OpenMP
is to be used or not.

Development builds need to limit optimisation in order that debug tools work
reliably. This also tend to make builds faster, thereby tightening the build
loop.

Production builds can take as long as needed in order to get maximum
performance.

The build system finds these different argument sets in the build script.
They are stored per compiler with modifications for different versions of the
compiler.

Standard set theory may be used to combine them so the union of the optimisation
set and the OpenMP set gives the arguments to compile with OpenMP at a
particular optimisation level.

Managing Misbehaving Compilers
++++++++++++++++++++++++++++++

The user has discovered that a particular source file causes a particular
optimisation stage of a certain compiler to go pathological and it takes an
hour to compile.

They include a rule in the build configuration for that component which
disables the problematic optimisation for the appropriate version of the
compiler.

When that source file is built, either while developing the component or when
the component is a prerequisite of another, the troublesome optimisation is
disabled.
