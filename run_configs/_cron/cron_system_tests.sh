#
# Build then rebuild all the MO projects, for both compilers.
# Use a fresh clone of Fab.
#
# Cron this to run every weekday midnight with
# 0 0 * * 1-5
# */15 * * * *

set -e

clear_term () {
    # Clears the terminal if there is one.
    # There isn't one when running from cron.
    if [ -n "${TERM}" ]
    then
        clear
    fi
}

rm -rf /tmp/persistent/cron_system_tests
mkdir /tmp/persistent/cron_system_tests
cd /tmp/persistent/cron_system_tests

clear_term
echo ""
echo "Cloning Fab"
echo ""
#git clone --branch master --depth 1 https://github.com/metomi/fab.git
git clone --branch cron_local_tests --depth 1 https://github.com/bblay/fab.git

clear_term
echo ""
echo "Build everything with gfortran, clean build"
echo ""
echo $PWD
./fab/run_configs/_cron/build_all_gfortran.sh

clear_term
echo ""
echo "Build everything again with gfortran, incremental build"
echo ""
./fab/run_configs/_cron/build_all_gfortran.sh

clear_term
echo ""
echo "Build everything with ifort, clean build"
echo ""
./fab/run_configs/_cron/build_all_ifort.sh

clear_term
echo ""
echo "Build everything again with ifort, incremental build"
echo ""
./fab/run_configs/_cron/build_all_ifort.sh

clear_term
echo "Built and rebuilt everything with both compilers"
