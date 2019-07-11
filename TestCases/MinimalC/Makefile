# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
.SUFFIXES:
.SUFFIXES: .c .o

CC = gcc

OBJECTS = program.o

verify: test.out test.expected
	diff $^

test.out: test
	./$< >$@

test.expected:
	printf "Hello world!\n" >$@

test: $(OBJECTS)
	@echo Linking $@
	$(CC) -o $@ $(OBJECTS)

.c.o:
	@echo Compiling $@
	$(CC) -o $@ -c $<

program.o: program.c

clean:
	rm *.o test test.out test.expected
