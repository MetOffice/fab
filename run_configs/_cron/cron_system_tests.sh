#
# Build then rebuild all the MO projects, for both compilers.
# Use a fresh clone of Fab.
#
# Cron this to run every weekday midnight with
# 0 0 * * 1-5
# */15 * * * *

set -e

rm -rf /tmp/persistent/cron_system_tests
mkdir /tmp/persistent/cron_system_tests
cd /tmp/persistent/cron_system_tests

#git clone --branch master --depth 1 https://github.com/metomi/fab.git
git clone --branch cron_local_tests --depth 1 https://github.com/bblay/fab.git

./fab/run_configs/_cron/build_all_gfortran.sh
./fab/run_configs/_cron/build_all_gfortran.sh

./fab/run_configs/_cron/build_all_ifort.sh
./fab/run_configs/_cron/build_all_ifort.sh
