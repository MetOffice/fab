Developing the Toy
##################

Being an introduction for those wishing to add to, or just experiment with, the
toy build system.


Obtaining Source
================

We use a fairly standard GitHub process. If you are interested in playing with
the toy as it stands, just clone the `primary repository`_.

.. _primary repository: https://github.com/MetOffice/ToyBuildSystem.git

On the other hand, if you are interested in submitting patches, fork that
repository, clone your fork, create branches on your clone, push them to your
fork and raise "pull requests" against the primary repository.

Review is required before a change is accepted.


Obtaining Dependencies
======================

A ``pyproject.toml`` file is provided which allows dependencies to be installed
using ``pip install`` at the project root directory.

If you are just looking to run the toy, use: ``pip install .``

Our development tools are available using: ``pip install .[dev]``

Finally, if you want to build the documentation, use: ``pip install .[doc]``


Running Development Examples
============================

In the directory ``test/development`` you will find example builds which may be
used to exercise the toy. ``skeleton.fabfile`` will build the "Skeleton"
application from the LFRic core repository. Meanwhile, ``atmosphere.fabfile``
will build the full atmosphere model from the LFRic applications repository.

Both these builds require XIOS, which does not currently support the
``pkg_config`` tool we use for locating prerequisite library resources. This
could be circumvented easily by providing our own local ``pkg_config`` files
for it. Instead we exercise the command-line override for 3rd party package
details, in the ``run`` script. Use it as a substitute for calling the toy
directly. e.g. ``run -j 4 -v --fabfile skeleton.fabfile``

.. note::
   Where possible test target code is retrieved from repositories using their
   public interface, e.g. HTTPS.

   This does not work for repositories with restricted access. In these cases
   SSH must be used. This, in turn, can cause the build to pause waiting for a
   pass-phrase to unlock your key matter.

   If the build seems to be stalled, check it isn't waiting for the SSH keys to
   be unlocked. If it is, you should be able to just enter your pass phrase as
   normal.


Development Tools
=================

We use the ``pytest`` tool for unit testing. Point it at the correct directory
with ``pytest test/unit-test``.

The ``mypy`` tool is used for static type analysis. It should run on both the
source and unit tests: ``mypy source test/unit-test``.

Source code style is enforced using the ``ruff`` tool. Source can be coerced
using ``ruff format source test/unit-test`` and checked using
``ruff check source test/unit-test``.


Discussion
==========

The primary repository has "Discussions" enabled. If you have any questions
feel free to ask them there.


Testing Against Bugged Source
=============================

Our developer tests make use of real project source in order to get a
real-world work out. The down side of this is that there can be bugs in that
source.

In order to progress while your bug fix is making its way through the review
process you can redirect the testing to a local working copy.

In the relevant `.fabfile` modify (for example):

.. code-block:: python

   GitHubRepository(
       "https://github.com/MetOffice/lfric_core#vn3.1",

to

.. code-block:: python

   FileTreeRepository(
       ".../path/to/working-copy",

You may need to add `FileTreeRepository` to an import statement.

It's probably a good idea to delete any build working directory you may have
hanging around.

Once your fix is on trunk you will need to change it back to a repository
service. Although now it will need to point to a revision on trunk, rather
than a tagged release.
