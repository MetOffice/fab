# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
.SUFFIXES:
.SUFFIXES: .x90 .f90 .F90 .o .mod

DIRECTORIES = kernels model

objects: kernels/my_kernel_mod.o algorithm_mod.o algorithm_mod_psy.o

%_psy.f90: %.x90
	@echo Psyclone $@
	psyclone -oalg $*.f90 -opsy $@  -d kernels \
                 -s $(realpath optimisation.py) \
                 -api dynamo0.3 -l -nodm $<

%.f90: %.x90
	@echo PSycloning $@
	psyclone -oalg $@ -opsy $*_psy.f90 -d kernels \
                 -s $(realpath optimisation.py) \
                 -api dynamo0.3 -l -nodm $<

%.o: %.f90
	@echo Compiling $@
	$(FC) -o $@ -module $(dir $@) $(addprefix -I,$(DIRECTORIES)) -c $<

%.mod: %.f90
	@echo Compiling $@
	$(FC) -o $*.o -module $(dir $@) $(addprefix -I,$(DIRECTORIES)) -c $<

algorithm_mod.o \
algorithm_mod.mod: algorithm_mod.f90 \
                   algorithm_mod_psy.mod model/field_mod.mod \
                   kernels/my_kernel_mod.mod
algorithm_mod.f90: algorithm_mod.x90 kernels/my_kernel_mod.f90 optimisation.py
algorithm_mod_psy.o \
algorithm_mod_psy.mod: algorithm_mod_psy.f90 \
                       model/field_mod.mod model/operator_mod.mod \
                       kernels/my_kernel_mod.mod
algorihm_mod_psy.f90: algorithm_mod.x90 kernels/my_kernel_mod.f90 \
                      optimisation.py
kernels/my_kernel_mod.o \
kernels/my_kernel_mod.mod: kernels/my_kernel_mod.f90 \
                           model/argument_mod.mod model/constants_mod.mod \
                           model/functionspace_mod.mod model/kernel_mod.mod \

model/field_mod.o \
model/field_mod.mod: model/field_mod.f90 model/functionspace_mod.mod

clean: ALWAYS
	-rm -r *.o *.mod kernels/*.o kernels/*.mod model/*.o model/*.mod test
	-rm *.pyc algorithm_mod.f90 algorithm_mod_psy.f90


ALWAYS:
