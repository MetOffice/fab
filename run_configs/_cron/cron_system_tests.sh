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

clear
echo ""
echo "Cloning Fab"
echo ""
#git clone https://github.com/metomi/fab.git
# until this is merged, we need something with this file in!

clear
echo ""
echo "Build everything with gfortran, clean build"
echo ""
echo $PWD
./fab/run_configs/_cron/build_all_gfortran.sh

clear
echo ""
echo "Build everything again with gfortran, incremental build"
echo ""
./fab/run_configs/_cron/build_all_gfortran.sh

clear
echo ""
echo "Build everything with ifort, clean build"
echo ""
./fab/run_configs/_cron/build_all_ifort.sh

clear
echo ""
echo "Build everything again with ifort, incremental build"
echo ""
./fab/run_configs/_cron/build_all_ifort.sh

clear
echo "Built and rebuilt everything with both compilers"
