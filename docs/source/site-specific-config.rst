.. _site_specific_config:

Site-Specific Configuration
***************************
A site might have compilers that Fab doesn't know about, or prefers
a different compiler from the Fab default. Fab abstracts the compilers
and other programs required during building as an instance of a
:class:`~fab.tools.Tool` class. All tools that Fab knows about, are
available in a :class:`~fab.tools.tool_repository.ToolRepository`.
That will include tools that might not be available on the current system.

Each tool belongs to a certain category of
:class:`~fab.tool.category.Category`. A `ToolRepository` can store
several instances of the same category.

At build time, the user has to create an instance of
:class:`~fab.tools.tool_box.ToolBox` and pass
it to the :class:`~fab.build_config.BuildConfig` object. This toolbox
contains all the tools that will be used during the build process, but
it can only store one tool per category. If a certain tool should not
be defined in the toolbox, the default from the `ToolRepository` will
be used. This is useful for many standard tools like `git`, `rsync`
etc that de-facto will never be changed.

.. note:: If you need to use for example different compilers for
          different files, you would implement this as a `meta-compiler`:
          implement a new class based on the existing
          :class:`~fab.tools.compiler.Compiler` class,
          which takes two (or more) compiler instances. Its
          :func:`~fab.tools.compiler.Compiler.compile_file`
          method can then decide (e.g. based on the path of the file to
          compile, or a hard-coded set of criteria) which compiler to use.

Category
==========
All possible categories are defined in
:class:`~fab.tool.category.Category`. If additional categories
should be required, they can be added.

Tool
====
Each tool must be derived from :class:`~fab.tools.Tool`.
The base class provides a `run` method, which any tool can
use to execute a command in a shell. Typically, a tool will
provide one (or several) custom commands to be used by the steps.
For example, a compiler instance provides a
:func:`~fab.tools.compiler.Compiler.compile_file` method.
This makes sure that no tool-specific command line options need
to be used in any Fab step, which will allow the user to replace any tool
with a different one.

New tools can easily be created, look at
:class:`~fab.tools.compiler.Gcc` or
:class:`~fab.tools.compiler.Icc`. Typically, they can just be
created by providing a different set of parameters in the
constructor.

This also allows compiler wrappers to be easily defined. For example,
if you want to use `mpif90` as compiler, which is a MPI-specific
wrapper for `ifort`, you can create this class as follows:

.. code-block::
    :linenos:
    :caption: Compiler wrapper

    from fab.tools import Ifort

    class MpiF90(Ifort):
        '''A simple compiler wrapper'''
        def __init__(self):
            super().__init__(name="mpif90-intel",
                             exec_name="mpif90")

.. note:: In `ticket 312 <https://github.com/metomi/fab/issues/312>`_ a better
        implementation of compiler wrapper will be implemented.

Tool Repository
===============
The :class:`~fab.tools.tool_repository.ToolRepository` implements
a singleton to access any tool that Fab knows about. A site-specific
startup section can add more tools to the repository:

.. code-block::
    :linenos:
    :caption: ToolRepository

    from fab.tools import ToolRepository

    # Assume the MpiF90 class as shown in the previous example

    tr = ToolRepository()
    tr.add_tool(MpiF90)   # the tool repository will create the instance

Compiler and linker objects define a compiler suite, and the `ToolRepository`
provides
:func:`~fab.tools.tool_repository.ToolRepository.set_default_compiler_suite`
which allows you to change the defaults for compiler and linker with
a single call. This will allow you to easily switch from one compiler
to another. If required, you can still change any individual compiler
after setting a default compiler suite, e.g. you can define `intel-classic`
as default suite, but set the C-compiler to be `gcc`.


Tool Box
========
The class :class:`~fab.tools.tool_box.ToolBox` is used to provide
the tools to be used by the build environment, i.e. the
`BuildConfig` object:

.. code-block::
    :linenos:
    :caption: ToolBox

    from fab.tools import Category, ToolBox, ToolRepository

    tr = ToolRepository()
    tr.set_default_compiler_suite("intel-classic")
    tool_box = ToolBox()
    ifort = tr.get_tool(Category.FORTRAN_COMPILER, "ifort")
    tool_box.add_tool(ifort)
    c_compiler = tr.get_default(Category.C_COMPILER)
    tool_box.add_tool(c_compiler)

    config = BuildConfig(tool_box=tool_box,
                         project_label=f'lfric_atm-{ifort.name}', ...)

The advantage of finding the compilers to use in the tool box is that
it allows a site to replace a compiler in the tool repository (e.g.
if a site wants to use an older gfortran version, say one which is called
`gfortran-11`). They can then remove the standard gfortran in the tool
repository and replace it with a new gfortran compiler that will call
`gfortran-11` instead of `gfortran`. But a site can also decide to
not support a generic `gfortran` call, instead adding different
gfortran compiler with a version number in the name.

If a tool category is not defined in the `ToolBox`, then
the default tool from the `ToolRepository` will be used. Therefore,
in the example above adding `ifort` is not strictly necessary (since
it will be the default after setting the default compiler suite to
`intel-classic`), and `c_compiler` is the default as well. This feature
is especially useful for the many default tools that Fab requires (git,
rsync, ar, ...).

.. code-block::
    :linenos:
    :caption: ToolBox

    tool_box = ToolBox()
    default_c_compiler = tool_box.get_tool(Category.C_COMPILER)


TODO
====
At this stage compiler flags are still set in the corresponding Fab
steps, and it might make more sense to allow their modification and
definition in the compiler objects.
This will allow a site to define their own set of default flags to
be used with a certain compiler by replacing or updating a compiler
instance in the Tool Repository
