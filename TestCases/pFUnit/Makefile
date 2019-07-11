# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
# This test simulates using the pFUnit framework for unit testing.
# As distributed it expects version 3.x.x of the framework. The
# processing script has changed name with version 4.x.x so you would
# need to change the PFRPOC macro to be "pfproc".
#
# The test assumes that the processing script is visible on the execution
# path. i.e. That it is included in the PATH environment variable.
#
.SUFFIXES:
.SUFFIXES: .pf .f90 .F90 .o .mod

FC = ifort
PFPROC = pFUnitParser.py

ifeq "x$(shell command -v $(PFPROC))" "x"
$(error Could not find the pFUnit processor on PATH)
endif

objects: stuff_mod.o stuff_test.o

.f90.o:
	@echo Compiling $@
	$(FC) -o $@ -c $<

.f90.mod:
	@echo Compiling $@
	$(FC) -o $*.o -c $<

.F90.o:
	@echo Compiling $@
	$(FC) -o $@ -I$(PFUNIT)/mod -c $<

.F90.mod:
	@echo Compiling $@
	$(FC) -o $*.o -I$(PFUNIT)/mod -c $<

.pf.F90:
	@echo Processing $@
	$(PFPROC) $< $@

stuff_mod.o stuff_mod.mod: stuff_mod.f90
stuff_test.o stuff_test_mod.mod: stuff_test.F90 stuff_mod.mod
stuff_test.F90: stuff_test.pf

clean:
	-rm *.o *.mod test stuff_test.F90
