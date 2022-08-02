#!/usr/bin/env bash
set -e

export FAB_WORKSPACE=$(pwd)/fab_system_tests
echo "using fab system test workspace" $FAB_WORKSPACE

SCRIPT_DIR=$( dirname "${BASH_SOURCE[0]}" )
cd "$SCRIPT_DIR"/../../run_configs
echo $(pwd)

#echo
#echo "build gcom object archive and shared object"
#echo
#cd gcom
#python -m grab_gcom
#python -m build_gcom_ar
#python -m build_gcom_so
#cd ..
#
#echo
#echo "build jules"
#echo
#cd jules
#python -m build_jules
#cd ..
#
#echo
#echo "build um"
#echo
#cd um
#python -m build_um
#cd ..

echo
echo "build lfric"
echo
cd lfric
#python -m grab_lfric
python -m gungho
python -m mesh_tools
python -m atm
cd ..
