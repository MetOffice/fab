

# test absolute filter with files in both the build source and build output folders




# pulls the root from the incoming file path and prepends it to the filter
#


# root/um in either source or output folder
filter1 = '/um/'
f"tmp-workspace/{BUILD_SOURCE}/um/foo.c"
f"tmp-workspace/{BUILD_OUTPUT}/um/foo.c"
f"tmp-workspace/{BUILD_SOURCE}/foo/um/foo.c"
f"tmp-workspace/{BUILD_OUTPUT}/foo/um/foo.c"

# um subfolder
filter2 = 'um/'
f"tmp-workspace/{BUILD_SOURCE}/um/foo.c"
f"tmp-workspace/{BUILD_OUTPUT}/um/foo.c"
f"tmp-workspace/{BUILD_SOURCE}/foo/um/foo.c"
f"tmp-workspace/{BUILD_OUTPUT}/foo/um/foo.c"
f"tmp-workspace/{BUILD_SOURCE}/foo_um/um/foo.c"
f"tmp-workspace/{BUILD_OUTPUT}/foo_um/um/foo.c"

filter3 = 'um'
f"tmp-workspace/{BUILD_SOURCE}/foo/bar/um.c"
f"tmp-workspace/{BUILD_OUTPUT}/foo/bar/um.c"


filter4 = '.f90'

f"tmp-workspace/{BUILD_SOURCE}/foo/bar/foo.c"
f"tmp-workspace/{BUILD_OUTPUT}/foo/bar/foo.c"












"/home/bb/g/f/tws/bs/temp/um/foobar/test.c"

"/home/bb/g/f/tws/bs/temp/um/foo/test.c"

"/home/bb/g/f/tws/bs/temp/foo-um/foo/test.c"


"/um/"

"/um"

"um/"

"um"



"/um/foo/"

"/um/foo"

"um/foo/"

"um/foo"



"a/b/c/d/e/f/g/h"

"a/b/c/d/e/f/g/h/"



"*.c"













"*include/"








