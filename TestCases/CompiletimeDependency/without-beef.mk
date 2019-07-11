$(info Building without beef)

FC = gfortran
CC = gcc

CFLAGS = 
FFLAGS = 

DIR = nobeef/

all: test-hillfort test-looper

test-hillfort: $(DIR)hillfort.out $(DIR)hillfort.expected
	diff $^

$(DIR)hillfort.out: $(DIR)hillfort
	./$< > $@

$(DIR)hillfort.expected: | $(DIR)
	printf "Input is 50\nHalving the number gives 25\n" > $@

test-looper: $(DIR)looper.out $(DIR)looper.expected
	diff $^

$(DIR)looper.out: $(DIR)looper
	./$< > $@

$(DIR)looper.expected: | $(DIR)
	printf "Test string\nTest string\nTest string\nTest string\nTest string\n" > $@

$(DIR)hillfort: $(DIR)hillfort.o
	@echo Linking $@
	$(FC) -o $@ $(FFLAGS) $^

$(DIR)looper: $(DIR)looper.o
	@echo Linking $@
	$(CC) -o $@ $(CFLAGS) $^

$(DIR)%.o: %.c | $(DIR)
	@echo Compiling $@
	$(CC) -o $@ $(CFLAGS) -c $<

$(DIR)%.o $(DIR)%.mod: %.f90 | $(DIR)
	@echo Compiling $@
	$(FC) -o $(DIR)$*.o $(FFLAGS) -c $<

$(DIR)%.o $(DIR)%.mod: %.F90 | $(DIR)
	@echo Compiling $@
	$(FC) -o $(DIR)$*.o $(FFLAGS) -c $<

$(DIR)hillfort.o: hillfort.F90
$(DIR)looper.o: looper.c bisto.h

$(DIR):
	mkdir -p $(DIR)

clean:
	-rm -r $(DIR)
