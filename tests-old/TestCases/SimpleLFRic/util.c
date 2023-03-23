#include "util.h"

int8_t eor_hash(void *block, int length) {
    int8_t hash = 0xff;
    for (unsigned int index = 0; index < length; ++index) {
        hash = hash ^ ((int8_t *)block)[index];
    }
    return hash;
}
