# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
.SUFFIXES:
.SUFFIXES: .f90 .o .mod

FC = ifort

OBJECTS = simple_impl.o simple_mod.o class_mod.o class_impl.o test.o

verify: test.out test.expected
	diff $^

test.out: test
	./$< >$@

test.expected:
	printf "Returner 14\n\nStart with 12\nAfter mangle 29\n" >$@

test: $(OBJECTS)
	@echo Linking $@
	$(FC) -o $@ $(OBJECTS)

.f90.o:
	@echo Building $@
	$(FC) -o $@ -c $<

.f90.mod:
	@echo Building $@
	$(FC) -o $*.o -c $<

simple_mod.o simple_mod.mod: simple_mod.f90
simple_impl.o: simple_impl.f90 simple_mod.mod
class_mod.o class_mod.mod: class_mod.f90
class_impl.o: class_impl.f90 class_mod.mod
test.o: test.f90 simple_mod.mod class_mod.mod

clean:
	rm *.o *.mod *.smod test test.out test.expected
