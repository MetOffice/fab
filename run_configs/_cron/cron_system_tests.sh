#!/usr/bin/env bash
# Build and rebuild all our Met Office example build projects, for both compilers.
# Use a fresh clone of Fab's main branch.
#
# Cron this to run every weekday midnight with
# 0 0 * * 1-5 bash -l -c "~/git/fab/run_configs/_cron/cron_system_tests.sh 2>&1 >/dev/null"
#

set -e

# remove last builds
rm -rf /tmp/persistent/cron_system_tests
mkdir /tmp/persistent/cron_system_tests
cd /tmp/persistent/cron_system_tests

# clone fab
git clone --branch main --depth 1 https://github.com/MetOffice/fab.git 2>&1 >/dev/null
# ...or if you're working on the system tests cron you can clone from your local repo like this
#git clone --branch 195_grab_git --depth 1 file:///home/h02/bblay/git/fab/ 2>&1 >/dev/null

# create a conda environment containing the head of trunk
1>&2 echo "removing old conda"
conda env remove --name cron-fab-system-tests
1>&2 echo "creating conda"
conda env create -f fab/envs/conda/dev_env.yml --name cron-fab-system-tests

# install the head of fab trunk
1>&2 echo "activating conda 1/2"
source /opt/conda/etc/profile.d/conda.sh
1>&2 echo "activating conda 2/2"
conda activate cron-fab-system-tests
1>&2 echo "installing head of fab trunk"
pip install -e fab[dev]
# we need to deactivate because otherwise, for some reason, the build scripts fail to import fab
1>&2 echo "deactivating conda"
conda deactivate

# gfortran
1>&2 echo ""
1>&2 echo "build all gfortran"
time ./fab/run_configs/_cron/build_all_gfortran.sh

1>&2 echo ""
1>&2 echo "rebuild all gfortran"
time ./fab/run_configs/_cron/build_all_gfortran.sh

# ifort
1>&2 echo ""
1>&2 echo "build all ifort"
time ./fab/run_configs/_cron/build_all_ifort.sh

1>&2 echo ""
1>&2 echo "rebuild all ifort"
time ./fab/run_configs/_cron/build_all_ifort.sh

# all done
1>&2 echo ""
1>&2 echo "all builds complete"
