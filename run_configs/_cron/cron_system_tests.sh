#
# Build and rebuild all our Met Office example build projects, for both compilers.
# Use a fresh clone of Fab's master branch.
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
#git clone --branch master --depth 1 https://github.com/metomi/fab.git 2>&1 >/dev/null
git clone --branch cron_local_tests --depth 1 file:///home/h02/bblay/git/fab/ 2>&1 >/dev/null

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
