Using Fab at the Met Office
===========================

For users working on Met Office desktop systems the following instructions may
prove useful.

Using Fab
~~~~~~~~~

If you just want to use Fab to build some source then there are a number of
fairly simple approaches.


Fortran Only
------------

If you don't need to build C, you can use this the modules in the "extra
software" collection::

.. code-block:: console

    $ module use $EXTRA_SOFTWARE
    $ module load python/3.7.0 support/fparser/0.16.0/python/3.7.0 fab/0.11.0/python/3.7.0

The Science I.T. group can provide the `EXTRA_SOFTWARE` path.


Fortran and C
-------------

If you need to build C, or you use conda environments anyway you can use the
:ref:`Conda<environment>` route to Fab-ulousness.

You will need to authenticate with Artifactory the first time you use Conda.
There is information regarding this on MetNet or ask Science I.T.


.. _Run Singularity:

Singularity Container
---------------------

You can run Fab in a singularity container as follows::

    singularity run oras://$URL/metomi/fab/MyImage:latest

If you need to use git from within the container, you'll need to set a couple of environment variables first::

    $ export SINGULARITY_BIND="/etc/pki/ca-trust/extracted/pem:/pem"
    $ export SINGULARITYENV_GIT_SSL_CAPATH="/pem"
    $ singularity shell oras://$URL/fab/MyImage:latest

The necessary URL is that normally used with singularity. Ask Science I.T. for
details.

See also :ref:`Instructions for building the image<Build Singularity>`.


Developing Fab
~~~~~~~~~~~~~~

If you want to develop Fab then there are some additional steps which may be
needed.


Mixing Conda and Environemnt Modules
------------------------------------

In order to have both an environment capable of building C files and modern
Fortran compilers and the LFRic library stack you will need an awkward
amalgimation of conda environment and environment modules.

The conda environment is created as follows::

    $ conda env create -f envs/conda/dev_env.yml
    $ conda activate sci-fab

Then :ref:`install fab<Install>`. This is done before any module commands.

Then the environment is set up *in a new terminal* as follows:

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


PyCharm
-------

Running ``pycharm-community`` from the command line, after activating an
environment using any of the above approaches, PyCharm will be able to run Fab,
the tests, etc.
You can `set the project interpreter <https://www.jetbrains.com/help/pycharm/configuring-python-interpreter.html>`_
to be that in the conda environment.


Rose
----
Various configs for building projects using Rose on SPICE can be found in
`run_configs <https://github.com/metomi/fab/tree/master/run_configs>`_.
