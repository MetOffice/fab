.. _Install:

Installing Fab
**************
You can install the latest release of `Fab from PyPI <https://pypi.org/project/sci-fab/>`_:

.. code-block:: console

    $ pip install sci-fab

The minimum Python dependencies (e.g. `fparser <https://github.com/stfc/fparser>`_)
will also be installed automatically.

Extra features
==============
You can install some extra Python packages to enable more features.
This will install `matplotlib <https://matplotlib.org/>`_ for producing metrics graphs after a run,
`psyclone <https://github.com/stfc/PSyclone>`_ for building LFRic, and more.

.. code-block:: console

    $ pip install sci-fab[features]

See also :ref:`Installation for Developers<development>`

Configuration
=============

You can optionally tell Fab where it's workspace should live.
This can be useful on systems where your home space is on a slower drive::

    export FAB_WORKSPACE=<fast_drive>/fab_workspace

By default, Fab will create a project workspaces inside ``~/fab-workspace``.
