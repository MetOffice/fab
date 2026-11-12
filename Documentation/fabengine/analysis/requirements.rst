Fab Requirements
################

Fab is an open-source Python tool designed to help build complex scientific
code. It is being designed with LFRic and the UM in mind – and thus some of the
possible build steps reflect the idiosyncrasies of those codebases – but it is
intended to be a generic tool, applicable to arbitrary (Fortran and C/C++)
code.

Overview
^^^^^^^^

Building LFRic is a complex process. Not only must the source code be compiled
and linked, but some components require pre-processing and some components must
be partially generated (either via the "PSyclone" source-to-source translator or
directly via "Templaterator"). There is also a rich set of configuration
metadata, largely in the form of namelist files, which define runtime variable
values and configuration options. Additionally, there are many compiler options
to define things like optimisation levels, etc. which can be specified to suit
particular configurations.

Having to manually coordinate all of these steps is untenable. Therefore, an
automated build system is required.

Requirements
^^^^^^^^^^^^

Implementations of Fab should be judged against these requirements.

1.0 Fab is comparable to (or faster than) the current build system
==================================================================

Ideally, Fab will be faster than the current build system. But at the very
least it should be within an order of magnitude.

2.0 Fab is "self-configuring"
=============================

Fab should not require complex configuration files nor runtime options to
successfully build code. This does not preclude the use of configuration files
(“fabfiles”). But where needed they should be minimal.

Fab should be able to automatically discover the source code files that need to
be built. It should also be able to discover the dependency hierarchy of those
files. And it should be able to determine the correct build steps required for
each file. For example, an ``.f90`` file requires compiling, an ``.F90`` file
requires pre-processing (to turn it into ``.f90`` file which then requires
compiling), and so on.

The specific options for each step can be configured as needed. But Fab will
default to sensible defaults, such as using the environment’s default C and
Fortran compilers.

2.1 Fab can discover code in the current directory, elsewhere on the filesystem, or on a remote (git or svn) repository
-----------------------------------------------------------------------------------------------------------------------

Individual files of a code base can be distributed across different locations.
Some files may be located in the current directory – the directory from which
fab is run. Some files may be located elsewhere on the network. In this case
utilities such as ``rsync`` could be used to access them. Some files may be
stored remotely on a versioning system such as Git or Subversion.

Fab should work seamlessly regardless of where code components are located.

2.2 Fab configuration can be project-wide, component-specific, environment-specific, or unspecified (i.e.: “zero-config mode”)
------------------------------------------------------------------------------------------------------------------------------

In addition to being distributed across different locations, a code base has a
hierarchy of files and directories. Fabfiles can be applied to any level of
that hierarchy, targeting any or all of the artefacts at that level and below.

.. note::

   Further explanation of project, component, environment and unspecified?

3.0 Fab is extensible
=====================

The Fab Framework should be easy to extend as new build steps arise. This can
most easily be accomplished in Python by implementing a step as an abstract
class that can be inherited from as needed.

4.0 Fab supports incremental builds
===================================

There is no need on subsequent iterative builds to rebuild code that has not
changed. This can be accomplished by hashing the pre-built (i.e.: before it has
been compiled, or templated, or pre-processed) state of each artefact. Only
those hashes that have changed need to re-apply the corresponding build step.
This implies, obviously, that each build step can access the hash of its input.

5.0 Fab produces metrics for each step of the build
===================================================

In order to judge the efficiency of the fab build process, profiling metrics
should be generated.

5.1 Fab displays feedback about progress during builds
------------------------------------------------------

As the build steps can take a very long time, it is useful to have feedback for
the user to confirm that fab is still making progress and is not hanging.
Obviously, this is most applicable when running fab interactively on the
command line rather than running it as a subprocess, as with suites.

5.2 Fab generates performance statistics that can be analysed after builds
--------------------------------------------------------------------------

At the end of a build, fab should generate profiling statistics describing the
CPU time and memory used for the overall build process as well as individual
build steps.

6.0 Fab can integrate testing into the build process
====================================================

Any sufficiently complex code base will include unit and functional tests. Fab
should be able to identify and run those tests. Depending on the usage
scenario, if a test fails the user may wish to stop the build process. Whether
or not fab terminates on test failure should be configurable.

Conclusions
^^^^^^^^^^^

Any implementation of fab should be judged against how well it meets these
requirements.
