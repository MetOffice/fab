###############################################################################
# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
# This test builds the same set of source with and without the BEEF macro set.
#
# This will cause the resulting executables to behave differently.
###############################################################################
# The Fortran compiler has to be gfortran as we use the -J argument to redirect
# module file output.
#
export FC = gfortran
export CC ?= gcc

# By default gmake sets FC to "f77" we need to detect that and force it to our
# default. If it is not set then we still have a default but we allow the user
# to override it.
#
ifeq "x$(shell command -v $(FC))" "x"
$(error Could not find gfortran on PATH)
endif

all: with-beef without-beef

with-beef:
	$(MAKE) -f with-beef.mk

without-beef:
	$(MAKE) -f without-beef.mk

clean:
	$(MAKE) -f with-beef.mk clean
	$(MAKE) -f without-beef.mk clean
