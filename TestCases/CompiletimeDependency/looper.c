#include <stdio.h>

#ifdef BEEF
#include "oxo.h"
#else
#include "bisto.h"
#endif

int main(int argc, char **argv) {
  int counter;

  for (counter=0; counter<LIMIT; ++counter) {
    printf("Test string\n");
  }

  return 0;
}
