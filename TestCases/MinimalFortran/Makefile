# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
.SUFFIXES:
.SUFFIXES: .f90 .F90 .o .mod

OBJECTS = program.o

test: $(OBJECTS)
	@echo Linking $@
	$(FC) -o $@ $(OBJECTS)

.f90.o:
	@echo Compiling $@
	$(FC) -o $@ -c $<

.f90.mod:
	@echo Compiling $@
	$(FC) -o $*.o -c $<

program.o: program.f90

clean: ALWAYS
	rm *.o *.mod test

ALWAYS:
