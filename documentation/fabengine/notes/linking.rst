The Trouble With Linking
########################

The process of linking compiled objects into an executable is often presented
as a dipole between static and dynamic.

When linking statically, everything required by the executable, including 3rd
part libraries, are combined at link time. By contrast, "dynamic" linking only
links 1st party objects at link time. Third party libraries are linked at run
time.

One of the primary advantages of dynamic linking is the reduction in duplicated
objects, combined into many executables. For instance, any Fortran program will
need to be linked to the Fortran run-time library. If this is done statically,
every executable has a copy of the Fortran run-time in it. When dynamic linking
is used there is only one copy and all executables use it.

The risk with dynamic linking is that a library being removed means that
otherwise functional executables stop working because they can't link to the
missing library.

It also makes it harder to be sure exactly what is being linked to what, which
can have implications for repeatability over time.

Half-way House
==============

There is a compromise solution which uses run-time linking but specifies
the paths (rather than just the identifier) of the libraries to be linked. This
is referred to as "rpath" linking due to the name of the argument passed to
the linker.

If a library is deleted or moved, this will still fail as, with the best will in the
world, the linker can't link a library which doesn't exist. It does solve the
determinism problem though; it must link to a specific library (or fail) rather
than unexpectedly linking to any version of the library.

Complications When Linking
==========================

In the past our environment modules have used the ``LD_FLAGS`` environment
variable to communicate library location using the ``-L`` argument. This allows
the linker to find the libraries specified by the project using ``-l``
notation.

It doesn't help at run-time though, so the modules also append to the
``LD_LIBRARY_PATH`` variable. This allows the libraries to be found at run time.

Recently we have moved to using "rpath" at link time and not modifying
``LD_LIBRARY_PATH``.

This interacts with our desire to make use of ``pkg_config`` which can provide
the ``-L`` arguments but not the "rpath". We can synthesis them from the big-L
values but we will probably want to support pure dynamic linking in the future
so "rpath" must be optional.

Future Issues
=============

There will be additional issues when we move to building by component. In this
model each sub-project will know how to build itself and projects higher in
the dependency tree will simply instruct them to do so.

In this model sub-projects will build themselves as libraries. In this case
we will have to consider whether they are building themselves as object
archives, only useful of static linking, or relocatable libraries, suitable
for dynamic linking.

Traveling Without Moving
========================

The "Spack" environment building tool claims to support a mode where a specific
path is provided for each library, instead of a searchable list of "R" paths.

This is potentially interesting as it takes load off the file system. A library
may be obtained directly rather than looking for it in all the "R" directories.
Reducing file system load is important when your file system is something like
"Lustre" which performs badly at that sort of task.
