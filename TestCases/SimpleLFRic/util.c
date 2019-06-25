#include "util.h"

uint8_t eor_hash(void *block, unsigned int length) {
    uint8_t hash = 0xff;
    for (unsigned int index = 0; index < length; ++index) {
        hash = hash ^ ((uint8_t *)block)[index];
    }
    return hash;
}
