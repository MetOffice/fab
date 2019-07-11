# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
.SUFFIXES:
.SUFFIXES: .c .f90 .F90 .o .mod

FC = gfortran
CC = gcc

ifdef BEEF
CFLAGS = -DBEEF
FFLAGS = -DBEEF
HILLFORT_OBJECTS = support_mod.o hillfort.o
LOOPER_OBJECTS = looper.o
else
CFLAGS = 
FFLAGS = 
HILLFORT_OBJECTS = hillfort.o
LOOPER_OBJECTS = looper.o
endif

all: hillfort looper

hillfort: $(HILLFORT_OBJECTS)
	@echo Linking $@
	$(FC) -o $@ $(FFLAGS) $(HILLFORT_OBJECTS)

looper: $(LOOPER_OBJECTS)
	@echo Linking $@
	$(CC) -o $@ $(CFLAGS) $(LOOPER_OBJECTS)

.c.o:
	@echo Compiling $@
	$(CC) -o $@ $(CFLAGS) -c $<

.f90.o:
	@echo Compiling $@
	$(FC) -o $@ $(FFLAGS) -c $<

.f90.mod:
	@echo Compiling $@
	$(FC) -o $*.o $(FFLAGS) -c $<

.F90.o:
	@echo Compiling $@
	$(FC) -o $@ $(FFLAGS) -c $<

.F90.mod:
	@echo Compiling $@
	$(FC) -o $*.o $(FFLAGS) -c $<

ifdef BEEF
hillfort.o: hillfort.F90 support_mod.mod
looper.o: looper.c oxo.h
support_mod.o support_mod.mod: support_mod.f90
else
hillfort.o: hillfort.F90
looper.o: looper.c bisto.h
endif

clean: ALWAYS
	rm *.o hillfort looper

ALWAYS:
