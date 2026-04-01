#!/bin/sh
# use this to see all the branches we expect to be created by create_repo.sh
set -e

tar -xf repo.tar.gz
mkdir see_all

fcm checkout "file://${PWD}/repo/proj/main/trunk" see_all/trunk
fcm checkout "file://${PWD}/repo/proj/main/branches/dev/person_a/file1_experiment_a" see_all/f1xa
fcm checkout "file://${PWD}/repo/proj/main/branches/dev/person_a/file1_experiment_b" see_all/f1xb
fcm checkout "file://${PWD}/repo/proj/main/branches/dev/person_b/file2_experiment@7" see_all/f2x_r7

# instead of just checking out r8, we might as well check the update works while we're here
fcm checkout "file://${PWD}/repo/proj/main/branches/dev/person_b/file2_experiment@7" see_all/f2x_r8
cd see_all/f2x_r7
fcm update --revision 8
cd ../..
