
*****
Usage
*****

Installation
============

To use Fab, first install it using pip.

.. code-block:: console

   (.venv) $ pip install fab

Configuration
-------------

You can optionally tell Fab where it's workspace should live.
Useful on systems where your home space is on a network drive,
which may not be as fast as your local hard drive.

    ``export FAB_WORKSPACE=/tmp/persistent/fab_workspace``

If you don't do this, Fab will create a workspace folder underneath the current working folder.

Conda
=====
Create a conda environment for running fab::

    conda env create -f environment.yml


Activate the new environment::

    conda activate fab

Install fab (from the fab folder)::

    python setup.py install

or::

    pip install .

Editable install
----------------
For Fab developers,
an `Editable install <https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs>`_::

    python setup.py develop

or::

    pip install -e .


Uninstall fab::

    python setup.py uninstall

or::

    pip uninstall sci_fab


Please be aware of some considerations when
`using pip and conda <https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#using-pip-in-an-environment>`_
together.