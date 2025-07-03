Introduction to BAF
===================
BAF, short for Build Architecture with Fab, is a command line interface
to the Fab build system. It is written in Python, and provides a pre-defined
framework for building binary files and libraries. It adds the following
features:

- It is object-oriented, making it easy to re-use and extend build scripts.
- It is driven by a command line interface. All options required for a build
  can be specified via command line options. For backward compatibility,
  it will use certain environment variables as default if they are defined.
- It supports site-specific configuration.
- It is very easy to extend.

Creating a build script using BAF will require writing a Python script,
and building an executable or library means executing this Python script.
BAF is just a wrapper around Fab, which on one hands makes it easier
to write scripts from scratch, but also means that if required the full
power of the Fab build system can be used.
As a consequence, knowledge of Fab is required, since certain operations
like checking out source files will use Fab commands.

Object-Oriented Design
----------------------
BAF itself is mostly a base class which is used to derive
application-specific build script from. These build scripts
can (and in general will need to) overwrite certain functions to tune
the behaviour. For example, the BAF base class provides a list
of useful command line options. But any application-specific script
can add additional command line options.

.. _command_line_options:

Command Line Options
--------------------
The BAF base class provides a list of commonly needed command line options.
Any application-specific build script can add additional command line options.
Invoking the BAF base class with the ``-h`` command line option gives a
description of the all options:

.. parsed-literal::

    usage: baf_base.py [-h] [--suite SUITE] [--available-compilers] [--fc FC] [--cc CC] [--ld LD] [--fflags FFLAGS] [--cflags CFLAGS] [--ldflags LDFLAGS] [--nprocs NPROCS] [--mpi] [--no-mpi]
                      [--openmp] [--no-openmp] [--openacc] [--host HOST] [--site SITE] [--platform PLATFORM] [--profile PROFILE]

    A Baf-based build system. Note that if --suite is specified, this will change the default for compiler and linker

    options:
      -h, --help            show this help message and exit
      --suite SUITE, -v SUITE
                            Sets the default suite for compiler and linker (default: None)
      --available-compilers
                            Displays the list of available compilers and linkers (default: False)
      --fc FC, -fc FC       Name of the Fortran compiler to use (default: $FC)
      --cc CC, -cc CC       Name of the C compiler to use (default: $CC)
      --ld LD, -ld LD       Name of the linker to use (default: $LD)
      --fflags FFLAGS, -fflags FFLAGS
                            Flags to be used by the Fortran compiler. The command line flags are appended after compiler flags defined in a site-specific setup and after getting flags from
                            the environment variable $FFLAGS. Therefore, this can be used to overwrite certain flags. (default: None)
      --cflags CFLAGS, -cflags CFLAGS
                            Flags to be used by the C compiler. The command line flags are appended after compiler flags defined in a site-specific setup and after getting flags from the
                            environment variable $CFLAGS. Therefore, this can be used to overwrite certain flags. (default: None)
      --ldflags LDFLAGS, -ldflags LDFLAGS
                            Flags to be used by the linker. The command line flags are appended after linker flags defined in a site-specific setup and after getting flags from the
                            environment variable $LDFLAGS. Therefore, this can be used to overwrite certain flags. (default: None)
      --nprocs NPROCS, -n NPROCS
                            Number of processes (default is 1) (default: 1)
      --mpi, -mpi           Enable MPI (default: True)
      --no-mpi, -no-mpi     Disable MPI (default: True)
      --openmp, -openmp     Enable OpenMP (default: True)
      --no-openmp, -no-openmp
                            Disable OpenMP (default: True)
      --openacc, -openacc   Enable OpenACC (default: True)
      --host HOST, -host HOST
                            Determine the OpenACC or OpenMP: either 'cpu' or 'gpu'. (default: cpu)
      --site SITE, -s SITE  Name of the site to use. (default: $SITE or 'default')
      --platform PLATFORM, -p PLATFORM
                            Name of the platform of the site to use. (default: $PLATFORM or 'default')
      --profile PROFILE, -pro PROFILE
                            Sets the compiler profile, choose from '['full-debug', 'fast-debug', 'production', 'unit-tests']'. (default: full-debug)

Some command line option have an environment variable as default
(e.g. ``-cc`` uses ``$CC`` as default). If the corresponding
environment variable is specified, its value will be used as default.
If the variable is not defined, the argument is considered to be not
specified.