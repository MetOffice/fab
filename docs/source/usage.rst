
Usage
*****
You must have an environment containing the compilers and linkers you need to build your project.

Conda
=====
.. note::
    *Internal Met Office Users*

    You may need to activate modules to gain access to command line tools. E.g::

        module use /data/users/lfric/modules/modulefiles.rhel7
        module load environment/lfric/gnu
        conda activate sci-fab


Containers
==========
You can create a development environment for running Fab using the docker file in Fab's github repo.
For example, PyCharm can use the interpreter inside the container and will automatically volume mount and PYTHONPATH
your source code.
