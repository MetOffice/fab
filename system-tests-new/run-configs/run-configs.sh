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
#cd gcom
#  ./grab_gcom.py
#  ./build_gcom_ar.py
#  ./build_gcom_so.py
#cd ..

echo
echo "building jules variants"
echo
#cd jules
#  ./build_jules.py
#  ./build_jules.py --two-stage
#  ./build_jules.py -opt=O2
#  ./build_jules.py -opt=O2 --two-stage
#cd ..

echo
echo "building um variants"
echo
cd um
  ./build_um.py
#  ./build_um.py --two-stage
#  ./build_um.py -opt=O2
#  ./build_um.py -opt=O2 --two-stage
cd ..

echo
echo "building lfric sub-projects variants"
echo
cd lfric
  ./grab_lfric.py

  ./gungho.py
#  ./gungho.py --two-stage
#  ./gungho.py -opt=O2
#  ./gungho.py -opt=O2 --two-stage

  ./mesh_tools.py
#  ./mesh_tools.py --two-stage
#  ./mesh_tools.py -opt=O2
#  ./mesh_tools.py -opt=O2 --two-stage

  ./atm.py
#  ./atm.py --two-stage
#  ./atm.py -opt=O2
#  ./atm.py -opt=O2 --two-stage
cd ..
