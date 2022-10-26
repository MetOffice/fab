#
# Build then rebuild all the MO projects, for both compilers.
# Use a fresh clone of Fab.
#
# Cron this to run every weekday midnight with
# 0 0 * * 1-5
# */15 * * * *

set -e

term_clear () {
    # Clears the terminal if there is one.
    # There isn't one when running from cron.
    if [ -n "${TERM}" ]
    then
        clear
    fi
}

term_echo () {
    # Echo if there is a terminal
    if [ -n "${TERM}" ]
    then
        echo "$1"
    fi
}

rm -rf /tmp/persistent/cron_system_tests
mkdir /tmp/persistent/cron_system_tests
cd /tmp/persistent/cron_system_tests

term_clear
term_echo ""
term_echo "Cloning Fab"
term_echo ""
#git clone --branch master --depth 1 https://github.com/metomi/fab.git
git clone --branch cron_local_tests --depth 1 https://github.com/bblay/fab.git

term_clear
term_echo ""
term_echo "Build everything with gfortran, clean build"
term_echo ""
term_echo $PWD
./fab/run_configs/_cron/build_all_gfortran.sh

term_clear
term_echo ""
term_echo "Build everything again with gfortran, incremental build"
term_echo ""
./fab/run_configs/_cron/build_all_gfortran.sh

term_clear
term_echo ""
term_echo "Build everything with ifort, clean build"
term_echo ""
./fab/run_configs/_cron/build_all_ifort.sh

term_clear
term_echo ""
term_echo "Build everything again with ifort, incremental build"
term_echo ""
./fab/run_configs/_cron/build_all_ifort.sh

term_clear
term_echo "Built and rebuilt everything with both compilers"
