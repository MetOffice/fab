# Create a Conda environment for running Fab with gfortran in Python 3.9.
# Export the spec for use with Picasso, which will also install Fab into this environment.
conda create -n py39 python=3.9
conda activate py39

conda install libclang
conda install python-clang
conda install -c conda-forge fparser
conda install -c conda-forge gfortran

# Export the environment as a spec file.
conda list --explicit > spec-file.txt
