# The best way to show how a test case should be built is to build it.
# While we don't have a build system we will use someone elses.
#
.SUFFIXES:
.SUFFIXES: .c .o

# By default gmake sets FC to "cc" we need to detect that and force it to our
# default. If it is not set then we still have a default but we allow the user
# to override it.
#
ifeq "$(origin CC)" "default"
export CC = gcc
else
export CC ?= gcc
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
	$(CC) -o $@ $(OBJECTS)

.c.o:
	@echo Compiling $@
	$(CC) -o $@ -c $<

program.o: program.c

clean:
	rm *.o test test.out test.expected
