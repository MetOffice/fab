# use this to see all the branches we expect to be created by create_repo.sh

tar -xf repo.tar.gz
mkdir see_all

svn checkout file://$PWD/repo/proj/trunk see_all/trunk
svn checkout file://$PWD/repo/proj/main/branches/dev/persona/file1_experiment_a see_all/f1xa
svn checkout file://$PWD/repo/proj/main/branches/dev/persona/file1_experiment_b see_all/f1xb
svn checkout file://$PWD/repo/proj/main/branches/dev/personb/file2_experiment@7 see_all/f2x_r7
svn checkout file://$PWD/repo/proj/main/branches/dev/personb/file2_experiment@8 see_all/f2x_r8
