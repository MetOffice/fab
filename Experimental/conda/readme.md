Create a conda environment for running fab
```
conda env create -f environment.yml
```


Activate the new environment

```
conda activate sci-fab
```

Install fab (from the fab folder)
```
python setup.py install
or
pip install .
```

[Editable install](https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs) for developers
```
python setup.py develop
or
pip install -e .
```

Uninstall fab
```
python setup.py uninstall
or
pip uninstall sci_fab
```


Please be aware of some considerations when
[using pip and conda](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#using-pip-in-an-environment)
together.