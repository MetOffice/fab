#!/bin/sh
# I had to do this a few times to get it right. It was a bit time consuming,
# and I realised it might be useful to put it in a script so we can
# reproduce it quickly and easily, and so others can see what's in the repo
# and change it easily in the future.
set -e

svnadmin create repo

# Create the initial files in trunk.
mkdir import

echo "This is sentence one in file one.

This is sentence two in file one.
" >> import/file1.txt

echo "This is sentence one in file two.

This is sentence two in file two.
" >> import/file2.txt

svn import import/ "file://${PWD}/repo/proj/main/trunk" -m "initial commit"
rm -rf import

# Create a branch which changes file 1.
svn copy "file://${PWD}/repo/proj/main/trunk" "file://${PWD}/repo/proj/main/branches/dev/person_a/file1_experiment_a" -m "create branch for file1 experiment a" --parents
svn checkout "file://${PWD}/repo/proj/main/branches/dev/person_a/file1_experiment_a" f1xa
cd f1xa
sed -i 's/This is sentence one in file one./This is sentence one, with Experiment A modification./' file1.txt
svn commit -m "experiment a modifications"
cd ..
rm -rf f1xa

# Create another branch which changes file 1, conflicting with the first branch.
svn copy "file://${PWD}/repo/proj/main/trunk" "file://${PWD}/repo/proj/main/branches/dev/person_a/file1_experiment_b" -m "create branch for file1 experiment b" --parents
svn checkout "file://${PWD}/repo/proj/main/branches/dev/person_a/file1_experiment_b" f1xb
cd f1xb
sed -i 's/This is sentence one in file one./This is sentence one, with Experiment B modification./' file1.txt
svn commit -m "experiment a modifications"
cd ..
rm -rf f1xb

# Create a branch which changes file 2, expecting it can be merged with one of the previous two branches without conflict.
svn copy "file://${PWD}/repo/proj/main/trunk" "file://${PWD}/repo/proj/main/branches/dev/person_b/file2_experiment" -m "create branch for file2 experiment" --parents
svn checkout "file://${PWD}/repo/proj/main/branches/dev/person_b/file2_experiment" f2x
cd f2x
sed -i 's/This is sentence two in file two./This is sentence two, with experimental modification./' file2.txt
# this is r7
svn commit -m "experimental modifications"
cd ..
rm -rf f2x

# Change file 2 again, so we can test the checkout/update code with different revisions
svn checkout "file://${PWD}/repo/proj/main/branches/dev/person_b/file2_experiment" f2x
cd f2x
sed -i 's/This is sentence two, with experimental modification./This is sentence two, with further experimental modification./' file2.txt
# this is r8
svn commit -m "further experimental modifications"
cd ..
rm -rf f2x

# zip it up
tar -czf repo.tar.gz repo
rm -rf repo
