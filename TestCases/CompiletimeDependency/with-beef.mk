$(info Building with beef)

export CFLAGS = -DBEEF
export FFLAGS = -DBEEF

DIR = beefy/

all: test-hillfort test-looper

test-hillfort: $(DIR)hillfort.out $(DIR)hillfort.expected
	diff $^

$(DIR)hillfort.out: $(DIR)hillfort
	./$< > $@

$(DIR)hillfort.expected: | $(DIR)
	printf "Input is 50\nNumber is 2 characters long\nHalving the number gives 25\n" > $@

test-looper: $(DIR)looper.out $(DIR)looper.expected
	diff $^

$(DIR)looper.out: $(DIR)looper
	./$< > $@

$(DIR)looper.expected: | $(DIR)
	printf "Test string\nTest string\nTest string\n" > $@

$(DIR)hillfort: $(DIR)support_mod.o $(DIR)hillfort.o
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
	$(FC) -o $(DIR)$*.o $(FFLAGS) -J$(DIR) -c $<

$(DIR)%.o $(DIR)%.mod: %.F90 | $(DIR)
	@echo Compiling $@
	$(FC) -o $(DIR)$*.o $(FFLAGS) -J$(DIR) -c $<

$(DIR)hillfort.o: hillfort.F90 $(DIR)support_mod.mod
$(DIR)looper.o: looper.c oxo.h
$(DIR)support_mod.o $(DIR)support_mod.mod: support_mod.f90

$(DIR):
	mkdir -p $@

clean:
	-rm -r $(DIR)
