# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
# This test expects the MPICH compiler wrapper scripts to be available on
# PATH. Furthermore it expects them to be wrapping Intel Fortran.
#
# It also expects the PSyclone source generator and pFUnit processor to be
# available on PATH.
#
# As recommended by the pFUnit developers it exptects a macro PFUNIT to
# contain the full path to the pFUnit install directory.
#
.SUFFIXES:
.SUFFIXES: .pf .f90 .F90 .o .mod

APP_OBJECTS = util.o util_mod.o \
              algorithm_mod.o algorithm_mod_psy.o \
              model/field_mod.o model/functionspace_mod.o model/mesh_mod.o \
              model/kernel_mod.o kernels/my_kernel_mod.o \
              thing.o
TEST_OBJECTS = kernels/my_kernel_mod.o my_kernel_test_mod.o driver.o

FC = mpif90
FFLAGS = -Ikernels -Imodel -I$(PFUNIT)/mod -debug full -traceback
CC = gcc
CFLAGS = -std=c99 -g
LFLAGS = -qopenmp -debug full -traceback
PSYCLONE = psyclone
PFPROC = pFUnitParser.py

ifneq "$(firstword $(shell $(FC) -show))" "ifort"
$(error Please build with MPICH for Intel Fortran)
endif

ifeq "x$(shell command -v $(PSYCLONE))" "x"
$(error Could not find the PSyclone script on PATH)
endif

ifeq "x$(shell command -v $(PFPROC))" "x"
$(error Could not find the pFUnit processor on PATH)
endif

all: thing test

thing: $(APP_OBJECTS)
	@echo Linking $@
	$(FC) -o $@ -g $(APP_OBJECTS) -lstdc++

test: $(TEST_OBJECTS)
	@echo Linking $@
	$(FC) $(LFLAGS) -o $@ -L$(PFUNIT)/lib $(TEST_OBJECTS) -l pfunit

%.o: %.c
	@echo Compiling $@
	$(CC) -o $@ $(CFLAGS) -c $<

%.o %.mod: %.f90
	@echo Compiling $@
	$(FC) -o $*.o $(FFLAGS) -module $(dir $@) -c $<

%.o %.mod: %.F90
	@echo Compiling $@
	$(FC) -o $*.o $(FFLAGS) -module $(dir $@) -c $<

%.f90 %_psy.F90: %.x90 optimisation.py
	@echo Generating $@
	$(PSYCLONE) -oalg $*.f90 -opsy $*_psy.F90 -d kernels \
                    -s $(realpath optimisation.py) -api dynamo0.3 -l -dm $<

util_mod.f90: util_mod.template # Really should be util.c
	@echo Generating $@
	# This cat is in lue of a generator
	cat util_mod.template > $@

.pf.F90:
	@echo Generating $@
	$(PFPROC) $< $@

driver.o: $(PFUNIT)/include/driver.F90 testSuites.inc
	@echo Compiling $@
	$(FC) -o $@ -I$(PFUNIT)/mod -c $<

testSuites.inc:
	@echo Creating $@
	echo ADD_TEST_SUITE\(my_kernel_test_mod_suite\) > $@

my_kernel_test_mod.o \
my_kernel_test_mod.mod: my_kernel_test_mod.F90 \
                        kernels/my_kernel_mod.mod model/constants_mod.mod
kernel_test_mod.F90: kernel_test_mod.pf

algorithm_mod.o \
algorithm_mod.mod: algorithm_mod.f90 algorithm_mod_psy.mod \
                   model/field_mod.mod kernels/my_kernel_mod.mod
algorithm_mod.f90: algorithm_mod.x90 kernels/my_kernel_mod.f90 optimisation.py
algorithm_mod_psy.o \
algorithm_mod_psy.mod: algorithm_mod_psy.F90 \
                       model/field_mod.mod model/operator_mod.mod \
                       kernels/my_kernel_mod.mod
algorithm_mod_psy.F90: algorithm_mod.x90 \
                       kernels/my_kernel_mod.f90 optimisation.py
kernels/my_kernel_mod.o \
kernels/my_kernel_mod.mod: kernels/my_kernel_mod.f90 model/mesh_mod.mod\
                           model/argument_mod.mod model/constants_mod.mod \
                           model/functionspace_mod.mod model/kernel_mod.mod

model/field_mod.o: model/field_mod.f90 \
                   model/constants_mod.mod model/functionspace_mod.mod \
                   model/mesh_mod.mod

util_mod.o: util_mod.f90 model/constants_mod.mod

thing.o: thing.f90 algorithm_mod.mod algorithm_mod_psy.mod  util_mod.mod \
         model/field_mod.mod

clean:
	-rm *.o *.mod *.pyc kernels/*.o kernels/*.mod model/*.o model/*.mod
	-rm testSuites.inc
	-rm algorithm_mod.f90 algorithm_mod_psy.F90 my_kernel_test_mod.F90
	-rm util_mod.f90
	-rm test thing
