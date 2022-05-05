##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

# Helper script to activate the sci-fab conda environment before invoking python, for rose suites.

. /etc/profile.d/conda.sh
conda activate sci-fab

BIN_FOLDER=$(dirname "$0")
export PYTHONPATH=$PYTHONPATH:$BIN_FOLDER

python -m $1
