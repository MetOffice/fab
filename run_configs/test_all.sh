set -e

cd ~/git/fab/run_configs/gcom
python -m grab_gcom
python -m build_gcom_ar
python -m build_gcom_so

cd ../jules
python -m build_jules

cd ../um
python -m build_um

cd ../lfric
python -m grab_lfric
python -m gungho
