# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
.SUFFIXES:
.SUFFIXES: .pf .f90 .F90 .o .mod

FC = ifort

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
	pFUnitParser.py $< $@

stuff_mod.o: stuff_mod.f90
stuff_test.o: stuff_test.F90 stuff_mod.mod
stuff_test.F90: stuff_test.pf

clean:
	-rm *.o *.mod test
