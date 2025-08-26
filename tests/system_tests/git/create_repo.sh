#!/bin/sh
# Create a repo with two conflicting branches.

set -e

mkdir repo
cd repo
git init .

echo "This is sentence one in file one.

This is sentence two in file one.
" >> file1.txt

git add file1.txt
git commit -m "initial commit"


# Create a branch which changes file 1.
git checkout -b experiment_a main
sed -i 's/This is sentence one in file one./This is sentence one, with Experiment A modification./' file1.txt
git commit -am "experiment a modifications"

# Create another branch which changes file 1, conflicting with the first branch.
git checkout -b experiment_b main
sed -i 's/This is sentence one in file one./This is sentence one, with Experiment B modification./' file1.txt
git commit -am "experiment a modifications"

git checkout main

# zip it up
cd ..
tar -czf repo.tar.gz repo
rm -rf repo
