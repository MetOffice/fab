.. _Environment:

Environment
***********
This page describes the environments in which Fab can be run.


.. _Requirements:

Requirements
============
The minimum dependencies for Fab to build a project are:

* Python >= 3.7
* Compiler
* Linker (or archiver, if building libraries)

If your project includes C code:

* libclang
* python-clang


Running Fab at The Met Office
=============================

VDI
---

Without clang
^^^^^^^^^^^^^
If you don't need to build C, you can use this modules command::

    $ module use $EXTRA_SOFTWARE
    $ module load fab/0.11.0/python/3.7.0


With clang
^^^^^^^^^^
This is currently a little awkward but will hopefully become simpler soon.
We use a combination of *module* commands and *conda* to get Fab running at The Met Office.
If you don't need to compile C code, you may not need conda.
We create the conda environment as follows::

    $ conda env create -f envs/conda/dev_env.yml
    $ conda activate sci-fab

Then :ref:`install fab<Install>`.

We do this in a before any module commands.
Then we set up our environment *in a new terminal* as follows.

For use with gfortran::

    $ module use $LFRIC_MODULES
    $ module load environment/lfric/gnu
    $ conda activate sci-fab
    $ PYTHONPATH=~/.conda/envs/sci-fab/lib/python3.7/site-packages:$PYTHONPATH

For use with ifort::

    $ module use $LFRIC_MODULES
    $ module load environment/lfric/ifort
    $ conda activate sci-fab
    $ PYTHONPATH=~/.conda/envs/sci-fab/lib/python3.7/site-packages:$PYTHONPATH

The PYTHONPATH line gives us access to a newer version of fparser in the conda environment.
Otherwise we get the older one from the modules commands.

PyCharm
^^^^^^^
If you run ``pycharm-community`` from the command line, after the above commands,
PyCharm will be able to run Fab, the tests, etc.
You can `set the project interpreter <https://www.jetbrains.com/help/pycharm/configuring-python-interpreter.html>`_
to be that in the conda environment.


Rose
----
Various configs for building projects using Rose on SPICE can be found in
`run_configs <https://github.com/metomi/fab/tree/master/run_configs>`_.


.. _Run Singularity:

Singularity
-----------
You can run Fab in a singularity container as follows::

    singularity run oras://metoffice-docker-local.jfrog.io/picasso/metomi/fab/MyImage:latest

If you need to use git from within the container, you'll need to set a couple of environment variables first::

    $ export SINGULARITY_BIND="/etc/pki/ca-trust/extracted/pem:/pem"
    $ export SINGULARITYENV_GIT_SSL_CAPATH="/pem"
    $ singularity shell oras://metoffice-docker-local.jfrog.io/picasso/metomi/fab/MyImage:latest


See also :ref:`Instructions for building the image<Build Singularity>`.

Authentication
^^^^^^^^^^^^^^
You'll need to authenticate if it's your first time::

    $ singularity remote login -u firstname.surname@metoffice.gov.uk docker://metoffice-docker-local.jfrog.io

You will be asked for your
`access token <https://metoffice.sharepoint.com/sites/TechnologyCommsSite/SitePages/Tooling/Artifactory/Artifactory-Cloud.aspx#using-api-keys>`_.


Outside The Met Office
======================

Docker
------
The dockerfile in `envs/docker <https://github.com/metomi/fab/tree/master/envs/docker>`_
can be used to create a container in which to run Fab.
This work-in-progress solution was tested on Windows, running Ubuntu in WSL.

Build the image::

    $ docker build -t fab envs/docker


Run the image, replacing ``<path_to_fab>`` with the path on your host machine and ``<user>`` with using your username::

    $ docker run --env PYTHONPATH=/fab -v <path_to_fab>/source:/fab -v /home/<user>:/home/<user> -it fab bash


Other
-----
You may need to ask your system administrator to install the above requirements.


Using Python venv
=================
Create an environment using Python's builtin `venv`

.. code-block:: console

    $ python -m venv <env name>
    $ cd <env name>
    $ . bin/activate

Then install fab

.. code-block:: console

    $ pip install sci-fab

You'll have to make sure the non-Python :ref:`requirements<Requirements>` are installed.
