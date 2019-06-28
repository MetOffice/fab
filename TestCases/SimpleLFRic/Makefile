# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
.SUFFIXES:
.SUFFIXES: .pf .f90 .F90 .cc .o .mod

APP_OBJECTS = io.o util.o util_mod.o \
              algorithm_mod.o algorithm_mod_psy.o \
              model/field_mod.o model/functionspace_mod.o model/mesh_mod.o \
              model/kernel_mod.o kernels/my_kernel_mod.o \
              thing.o
TEST_OBJECTS = kernels/my_kernel_mod.o kernel_test_mod.o driver.o

FC = mpif90
FFLAGS = -Ikernels -Imodel -I$(PFUNIT)/mod
CC =gcc
CFLAGS = -std=c99
LFLAGS = -qopenmp

all: thing test

thing: $(APP_OBJECTS)
	@echo Linking $@
	$(FC) -o $@ $(APP_OBJECTS) -lstdc++

test: $(TEST_OBJECTS)
	@echo Linking $@
	$(FC) $(LFLAGS) -o $@ -L$(PFUNIT)/lib $(TEST_OBJECTS) -l pfunit

%.o: %.cc
	@echo Compiling $@
	$(CXX) -o $@ -c $<

%.o: %.c
	@echo Compiling $@
	$(CC) -o $@ $(CFLAGS) -c $<

%.o %.mod: %.f90
	@echo Compiling $@
	$(FC) -o $*.o $(FFLAGS) -module $(dir $@) -c $<

%.o %.mod: %.F90
	@echo Compiling $@
	$(FC) -o $*.o $(FFLAGS) -module $(dir $@) -c $<

%.f90 %_psy.F90: %.x90
	@echo Generating $@
	psyclone -oalg $*.f90 -opsy $*_psy.F90 -d kernels \
                 -s $(realpath optimisation.py) -api dynamo0.3 -l -dm $<

util_mod.f90: util_mod.template # Really should be util.c
	@echo Generating $@
	# This cat is in lue of a generator
	cat util_mod.template > $@

.pf.F90:
	@echo Generating $@
	pFUnitParser.py $< $@

driver.o: $(PFUNIT)/include/driver.F90 testSuites.inc
	@echo Compiling $@
	$(FC) -o $@ -I$(PFUNIT)/mod -c $<

testSuites.inc:
	@echo Creating $@
	echo ADD_TEST_SUITE\(kernel_test_mod_suite\) > $@

kernel_mod.o: kernel_mod.f90
kernel_test_mod.o: kernel_test_mod.F90
kernel_test_mod.F90: kernel_test_mod.pf

algorithm_mod.o: algorithm_mod.f90 algorithm_mod_psy.mod \
                 model/field_mod.mod kernels/my_kernel_mod.mod
algorithm_mod.f90: algorithm_mod.x90 kernels/my_kernel_mod.mod optimisation.py
algorithm_mod_psy.o: algorithm_mod_psy.F90 \
                     model/field_mod.mod model/operator_mod.mod \
                     kernels/my_kernel_mod.mod
algorithm_mod_psy.F90: algorithm_mod.x90 kernels/my_kernel_mod.f90 optimisation.py
kernels/my_kernel_mod.o: kernels/my_kernel_mod.f90 model/mesh_mod.mod\
                         model/argument_mod.mod model/constants_mod.mod \
                         model/functionspace_mod.mod model/kernel_mod.mod

model/field_mod.o: model/field_mod.f90 \
                   model/constants_mod.mod model/functionspace_mod.mod \
                   model/mesh_mod.mod

util_mod.o: util_mod.f90 model/constants_mod.mod

thing.o: thing.f90 algorithm_mod.mod algorithm_mod_psy.mod  util_mod.mod \
         model/field_mod.mod

clean: ALWAYS
	-rm *.o *.mod *.pyc kernels/*.o kernels/*.mod model/*.o model/*.mod
	-rm testSuites.inc
	-rm algorithm_mod.f90 algorithm_mod_psy.F90 kernel_test_mod.F90
        -rm util_mod.f90
	-rm test thing

ALWAYS:
