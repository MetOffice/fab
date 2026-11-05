#!/bin/sh
##############################################################################
# Launch three runs of the toy build system and time their run.
#
# In order to get reliable timings we always reserve a full node in order to
# avoid resource contention. Particularly the filing system.
#
# As such, change the number of worker threads using the WORKERS variable, not
# the --ntasks batch manager directive.
##############################################################################
#SBATCH --wait
#SBATCH --array=0-2
#SBATCH --time=00:10:00
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --mem=16g
#SBATCH --gres=tmp:1024
#SBATCH -o %j.out
#SBATCH -e %j.err

WORKERS=16
QUEUE_STRATEGY=always_to_back
APPLICATION=skeleton

# For performance benchmark run
#
WORKSPACE=$TMPDIR

# Alternatively, for debugging
#
# WORKSPACE=$(readlink -f ../temporary)
# rm -rf $WORKSPACE

echo Building with $WORKERS workers
rsync -a ../../ "$WORKSPACE/"

module load lfric
module unload sci-fab

cd "$WORKSPACE" || exit 1
python3.12 -m venv venv
. venv/bin/activate
pip install --upgrade pip
pip install .

cd "$WORKSPACE/test/development" || exit 1
time ./run -j $WORKERS \
    --work-dir="$WORKSPACE/work" --no-monitor \
    --queue-strategy=$QUEUE_STRATEGY --fabfile=$APPLICATION.fabfile \
    --no-tests --timing-file=timing.$WORKERS.txt

EXE_skeleton=skeleton
EXE_atmosphere=lfric_atm
FILENAME=EXE_$APPLICATION
ls -l "$WORKSPACE/work/$(eval echo \"\$$FILENAME\")"
