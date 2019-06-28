# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
.SUFFIXES:
.SUFFIXES: .c .o

OBJECTS = program.o

test: $(OBJECTS)
	@echo Linking $@
	$(CC) -o $@ $(OBJECTS)

.c.o:
	@echo Compiling $@
	$(CC) -o $@ -c $<

program.o: program.c

clean: ALWAYS
	rm *.o test

ALWAYS:
