# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
# This test builds the same set of source with and without the BEEF macro set.
#
# This will cause the resulting executables to behave differently.
#
all: with-beef without-beef

with-beef:
	$(MAKE) -f with-beef.mk

without-beef:
	$(MAKE) -f without-beef.mk

clean:
	$(MAKE) -f with-beef.mk clean
	$(MAKE) -f without-beef.mk clean
