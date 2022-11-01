set -e

# set up the MO gfortran environment with Fab in conda
module use /data/users/lfric/modules/modulefiles.rhel7
module load environment/lfric/gnu
source /opt/conda/etc/profile.d/conda.sh
conda activate sci-fab

cd /tmp/persistent/cron_system_tests
./fab/run_configs/build_all.py
