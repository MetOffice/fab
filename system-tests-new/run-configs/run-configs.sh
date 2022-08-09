#!/usr/bin/env bash
set -e

export FAB_WORKSPACE=$(pwd)/fab_system_tests
echo "using fab system test workspace" $FAB_WORKSPACE

# find the run_configs folder
SCRIPT_DIR=$( dirname "${BASH_SOURCE[0]}" )
cd "$SCRIPT_DIR"/../../run_configs
echo $(pwd)

echo
echo "building gcom variants"
echo
cd gcom
./grab_gcom.py
./build_gcom_ar.py
./build_gcom_so.py
cd ..

echo
echo "building jules variants"
echo
cd jules
./build_jules.py
./build_jules.py --two-stage
cd ..

echo
echo "building um variants"
echo
cd um
./build_um.py
./build_um.py --two-stage
cd ..

echo
echo "building lfric sub-projects variants"
echo
cd lfric
./grab_lfric.py
./grab_lfric.py --two-stage
./gungho.py
./gungho.py --two-stage
./mesh_tools.py
./mesh_tools.py --two-stage
./atm.py
cd ..
