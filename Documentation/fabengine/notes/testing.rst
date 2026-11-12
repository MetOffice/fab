Testing As Part of a Build
##########################

In line with common good engineering practice we want to include various kinds
of functional testing into our build system. Specifically unit and integration
testing. System and the other kind of integration testing are better handled by
processes outside the build.

Unit Testing
============

Unit testing is currently implemented using the `pFUnit`_ framework.

.. _`pFUnit`: https://github.com/Goddard-Fortran-Ecosystem/pFUnit

It is designed to aggregate all the tests into a single executable which is
then invoked to run the tests. While this is fine for small projects it has
two major scaling problems. The first is just size, the executable can become
very large which will lead to very long link times.

The second being that it can take a substantial amount of time for a lot of
tests to run. This is unavoidable and part of the acceptable cost of testing
when everything is passing. During development, though, it can be unacceptably
costly to rerun the whole suite in order to run a single test.

A solution to this problem is to build each test file into its own executable
and trust to the build system to manage this and run all the tests. This
solution is much superior for development as a single set of tests can be
run repeatedly by hand without having to run all the others.

In reality we likely want both approaches available to us. The
executable-per-file for testing and the single-monolithic-executable for
porting when we want to know how many problems are outstanding.

There is a technical problem with pFUnit's implementation in that it does not
adequately isolate the running tests so global values from one can leek into
others. The executable-per-test approach also minimises this issue.

Implementation in the Toy
~~~~~~~~~~~~~~~~~~~~~~~~~

Executable-per-file has been implemented already. This easily falls out of
the task queue since each `.pf` file encountered raises an associated driver
compile, executable link and executable run.

Implementing the monolithic executable approach will require a list of `.pf`
files encountered to be compiled during code scan. Only once the scan is
completed can a driver be compiled and run.

This is the same problem as linking any executable and is currently handled by
holding a list in the "database" object shared between workers. We can't get
away from the need to manage this list but we may be able to clean up the
implementation.

A New Approach?
---------------

An empty link object might be raised and lodged with the database when
its need is determined. (e.g. finding a unit test or a "program" program unit)
Subsequent discoveries are added to this action object which is then added to
the queue once "full."

This moves the instantiation of the final action from the end of the process
to the beginning. This may remove the need to pass data down the process only
for use by this final action.

Cost of Unit Testing
~~~~~~~~~~~~~~~~~~~~

Very few things are free and unit testing is not one of them. Tests need to be
built and run, which costs resources.

To get an idea of what we are dealing with, this plot shows the difference
between a straight build of skeleton and a build with the unit tests
enabled.

.. attention::
   Due to the requirement for MPI to be initialised for any feigned
   configuration it is not possible to complete a build. As such there are no
   timings yet.

.. plot::

   from _plots.plot import clustered_bar_plot

   timings = {
       'Without Unit Tests': ['00:00', '00:00', '00:00', '00:00'],
       'With Unit Tests': ['00:00', '00:00', '00:00', '00:00']
   }
   workers = (1, 2, 3, 4)

   clustered_bar_plot(timings,
                      workers, "Workers",
                      "Minutes to complete, lower is better",
                      "Build of Skeleton application from clean")

Building with unit tests enabled causes tests from all the prerequisite
libraries to be run. These are: Infrastructure, Driver component,
Science component, Inventory component and XIOS component.

This is different to the current build system which only builds and runs unit
tests for the top level project. In this case that would be "skeleton" which
has only one test.

Due to this the times for the current build system are not presented as it
would be comparing apples and oranges.
