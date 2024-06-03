.. _site_specific_config:

Site-Specific Configuration
***************************
A site might have compilers that Fab doesn't know about, or prefers
a different compiler from the Fab default. Fab abstracts the compilers
and other programs required during building as an instance of a
:class:`~fab.tools.tool.Tool` class. All tools that Fab knows about, are
available in a :class:`~fab.tools.tool_repository.ToolRepository`.
That will include tools that might not be available on the current system.

Each tool belongs to a certain category of
:class:`~fab.tool.categories.Categories`. A `ToolRepository` can store
several instances of the same category.

At build time, the user has to create an instance of
:class:`~fab.tools.tool_box.ToolBox` and pass
it to the :class:`~fab.build_config.BuildConfig` object. This toolbox
contains all the tools that will be used during the build process, but
it can only store one tool per category. If a certain tool should not
be defined in the toolbox, the default from the `ToolRepository` will
be used. This is useful for many standard tools like `git`, `rsync`
etc that de-facto will never be changed.


Categories
==========
All possible categories are defined in
:class:`~fab.tool.categories.Categories`. If additional categories
should be required, they can be added.

Tool
====
Each tool must be derived from :class:`~fab.tools.tool.Tool`.
The base class provides a `run` method, which any tool can
use to execute a command in a shell. Typically, a tool will
provide one (or several) custom commands to be used by the steps.
For example, a compiler instance provides a
:func:`~fab.tools.compiler.Compiler.compile_file` method.
This makes sure that no tool-specific command line options need
to be used in any Fab step, which will allow to replace any tool
with a different one.

New tools can easily be created, look at
:class:`~fab.tools.compiler.Gcc` or
:class:`~fab.tools.compiler.Icc`. Typically, they can just be
created by providing a different set of parameters in the
constructor.

This also allows to easily define compiler wrapper. For example,
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

Compiler and linker objects define a vendor, and the `ToolRepository`
provides
:func:`~fab.tools.tool_repository.ToolRepository.set_default_vendor`
which allows you to change the defaults for compiler and linker with
a single call. This will allow you to easily switch from one compiler
to another.

Tool Box
========
The class :class:`~fab.tools.tool_box.ToolBox` is used to provide
the tools to be use to the build environment, i.e. the
BuildConfig object:

.. code-block::
    :linenos:
    :caption: ToolBox

    from fab.tools import Categories, ToolBox, ToolRepository

    tr = ToolRepository()
    tr.set_default_vendor("intel")
    tool_box = ToolBox()
    ifort = tr.get_tool(Categories.FORTRAN_COMPILER, "ifort")
    tool_box.add_tool(ifort)
    c_comp = tr.get_default(Categories.C_COMPILER)
    tool_box.add_tool(c_comp)

    config = BuildConfig(tool_box=tool_box,
                         project_label=f'lfric_atm-{ifort.name}', ...)

The advantage of finding the compilers to use in the tool box is that
it allows a site to replace a compiler in the tool repository (e.g.
if a site wants to use an older gfortran version, say one which is called
`gfortran-11`). They can then remove the standard gfortran in the tool
repository and replace it with a new gfortran compiler that will call
`gfortran-11` instead of `gfortran`.

If a tool category is not defined in the `ToolBox`, then
the default tool from the `ToolRepository` will be used. Therefore,
in the example above adding `ifort` is not strictly necessary (since
it will be the default after setting the default vendor to `intel`),
and `c_comp` is the default as well. This feature is especially useful
for the many default tools that Fab requires (git, rsync, ar, ...).

.. code-block::
    :linenos:
    :caption: ToolBox

    tool_box = ToolBox()
    default_c_compiler = tool_box.get_tool(Categories.C_COMPILER)


TODO
====
At this stage compiler flags are still set in the corresponding Fab
steps, and it might make more sense to allow their modification and
definition in the compiler objects.
This will allow a site to define their own set of default flags to
be used with a certain compiler by replacing or updating a compiler
instance in the Tool Repository
