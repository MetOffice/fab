Introduction to the Fab Base Class
==================================
Fab provides a base class, which provides a command line interface
to the Fab build system. It is written in Python, and provides a pre-defined
framework for building binary files and libraries. It adds the following
features:

- It is object-oriented, making it easy to re-use and extend build scripts.
- It is driven by a command line interface. All options required for a build
  can be specified via command line options. For backward compatibility,
  it will use certain environment variables as default if they are defined.
- It supports site-specific configuration.
- It is very easy to extend.

Creating a build script using the Fab base class will require writing a Python
script, and building an executable or library means executing this Python
script. Knowledge of Fab is required when using the base class, since certain
operations like checking out source files will use Fab commands.

Object-Oriented Design
----------------------
The Fab base class is used to derive application-specific build script from.
These build scripts can (and in general will need to) overwrite certain functions
to tune the behaviour. For example, the base class provides a list
of useful command line options. But any application-specific script
can add additional command line options.

.. _command_line_options:

Command Line Options
--------------------
The base class provides a list of commonly needed command line options.
Any application-specific build script can add additional command line options.
Invoking the base class itself with the ``-h`` command line option gives a
description of the all options:

.. parsed-literal::

    usage: fab_base.py [-h] [--suite SUITE] [--available-compilers] [--fc FC] [--cc CC] [--ld LD] [--fflags FFLAGS] [--cflags CFLAGS] [--ldflags LDFLAGS] [--nprocs NPROCS]
                       [--mpi] [--no-mpi] [--openmp] [--no-openmp] [--openacc] [--host HOST] [--site SITE] [--platform PLATFORM]

    A Fab-based build system. Note that if --suite is specified, this will change the default for compiler and linker

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
                            Flags to be used by the Fortran compiler. The command line flags are appended after compiler flags defined in a site-specific setup and after getting
                            flags from the environment variable $FFLAGS. Therefore, this can be used to overwrite certain flags. (default: None)
      --cflags CFLAGS, -cflags CFLAGS
                            Flags to be used by the C compiler. The command line flags are appended after compiler flags defined in a site-specific setup and after getting flags
                            from the environment variable $CFLAGS. Therefore, this can be used to overwrite certain flags. (default: None)
      --ldflags LDFLAGS, -ldflags LDFLAGS
                            Flags to be used by the linker. The command line flags are appended after linker flags defined in a site-specific setup and after getting flags from
                            the environment variable $LDFLAGS. Therefore, this can be used to overwrite certain flags. (default: None)
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


Some command line option have an environment variable as default
(e.g. ``-cc`` uses ``$CC`` as default). If the corresponding
environment variable is specified, its value will be used as default.
If the variable is not defined, the argument is considered to be not
specified.

.. toctree::
   :maxdepth: 2
   :caption: FabBase class
   :hidden:

   processing
   config
   examples
   usage_patterns
   