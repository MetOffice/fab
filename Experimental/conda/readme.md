Create a conda environment for running fab
```
conda env create -f environment.yml
```


Activate the new environment

```
conda activate fab
```

Install fab (from the fab folder)
```
pip install .
```

Please be aware of some considerations when
[using pip and conda](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#using-pip-in-an-environment)
together.