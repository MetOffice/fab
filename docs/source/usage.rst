

Usage
*****

Installation
============

To use Fab, download and install it::

    git clone https://github.com/metomi/fab.git
    pip install fab

Conda
-----
To create a conda environment for running fab::

    git clone https://github.com/metomi/fab.git
    conda env create -f fab/dev_env.yml

Activate the new environment::

    conda activate sci-fab

Install fab::

    pip install fab


Uninstall fab
-------------
To uninstall fab::

    pip uninstall fab



Configuration
=============

You can optionally tell Fab where it's workspace should live.
Useful on systems where your home space is on a network drive,
which may not be as fast as your local hard drive::

    export FAB_WORKSPACE=/tmp/persistent/fab_workspace

If you don't do this, Fab will create a project workspace underneath ``~/fab-workspace``.


Development
===========

Editable install
----------------
For Fab developers, an
`Editable install <https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs>`_
will allow you to change the code without reinstalling Fab every time::

    pip install -e fab

Please be aware of some considerations when
`using pip and conda <https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#using-pip-in-an-environment>`_
together.
