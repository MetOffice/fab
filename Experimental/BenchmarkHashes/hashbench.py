#!/usr/bin/env python3
import hashlib
from pathlib import Path
import time
import zlib

_ITERATIONS = 10


def from_zlib(test_data):
    for method in (zlib.crc32, zlib.adler32):
        print(f"Algorithm: {method}", end='')
        start_time = time.time()
        for iteration in range(_ITERATIONS):
            _ = method(test_data, 1)
        end_time = time.time()
        print(f" - {(end_time - start_time) / _ITERATIONS}")


def from_hashlib(test_data):
    for method in hashlib.algorithms_available:
        print(f"Algorithm: {method.rjust(10)} - ", end='')
        hasher = hashlib.new(method)
        start_time = time.time()
        for iteration in range(_ITERATIONS):
            _ = hasher.update(test_data)
        end_time = time.time()
        elapsed = (end_time - start_time) / _ITERATIONS
        print(elapsed)


def main():
    test_file = Path(__file__).parent / 'psykal_lite_mod.F90'
    test_data = test_file.read_bytes()
    from_zlib(test_data)
    from_hashlib(test_data)


if __name__ == '__main__':
    main()
