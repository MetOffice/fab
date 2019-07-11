THIS_DIR := $(dir $(lastword $(MAKEFILE_LIST)))

TEST_DIRS := $(shell find $(THIS_DIR) -type d -mindepth 1 -maxdepth 1 -print)

run: $(addprefix run/, $(TEST_DIRS))

run/%:
	$(MAKE) -C $*

clean: $(addprefix clean/, $(TEST_DIRS))

clean/%:
	$(MAKE) -C $* clean
