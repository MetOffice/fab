.. _install:

Installation
************
Instructions for downloading and installing Fab.

Latest release
==============
You can install the latest release of Fab from PyPI::

    pip install sci-fab

Cutting Edge
============
If you want the newest features, you can download the repo from github::

    git clone https://github.com/metomi/fab.git

Then install the folder::

    pip install ./fab


Configuration
=============

You can optionally tell Fab where it's workspace should live.
This can be useful on systems where your home space is on a slower network drive::

    export FAB_WORKSPACE=/tmp/persistent/fab_workspace

If you don't do this, Fab will create a project workspace underneath ``~/fab-workspace``.


Run Environment
===============
You must have an environment with the compilers and linkers you need to build your project.

Conda
-----
You can create a conda environment for running fab from a yaml file in the repo::

    git clone https://github.com/metomi/fab.git
    conda env create -f fab/dev_env.yml

Activate the new environment::

    conda activate sci-fab

Install fab::

    pip install ./fab



.. note::
    *Internal Met Office Users*

    *After* you've created your Conda environment with Fab installed,
    you may need to activate modules in a new terminal to gain access to command line tools. E.g::

        module use /data/users/lfric/modules/modulefiles.rhel7
        module load environment/lfric/gnu
        conda activate sci-fab


Containers
----------
You can create a development environment for running Fab using the docker file in Fab's github repo.
For example, PyCharm can use the interpreter inside the container and will automatically volume mount and PYTHONPATH
your source code.


Developers
==========

Editable install
----------------
For Fab developers, an
`Editable install <https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs>`_
will allow you to change the code without reinstalling Fab every time::

    pip install -e <path to fab>

Please be aware of some considerations when
`using pip and conda <https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#using-pip-in-an-environment>`_
together.
