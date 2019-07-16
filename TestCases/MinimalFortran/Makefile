# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
.SUFFIXES:
.SUFFIXES: .f90 .F90 .o .mod

# By default gmake sets FC to "f77" we need to detect that and force it to our
# default. If it is not set then we still have a default but we allow the user
# to override it.
#
ifeq "$(origin FC)" "default"
FC = ifort
else
FC ?= ifort
endif

OBJECTS = program.o

verify: test.out test.expected
	diff $^

test.out: test
	./$< >$@

test.expected:
	printf "Hello world!\n" >$@

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

clean:
	-rm *.o test test.out test.expected
