# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution

'''
Source reading tools for Fortran format.
'''
import re
from typing import Generator
from pathlib import Path


def sourcefile_iter(filepath: Path) -> Generator[str, None, None]:
    '''
    Generator to return each line of a source file; the lines
    are sanitised to remove comments and collapse the result
    of continuation lines whilst also trimming away as much
    whitespace as possible
    '''
    with filepath.open('r') as source:
        line_buffer = ''
        for line in source:

            # Remove comments - we accept that an exclamation mark
            # appearing in a string will cause the rest of that line
            # to be blanked out, but the things we wish to parse
            # later shouldn't appear after a string on a line anyway
            line = re.sub(r'!.*', '', line)

            # If the line is empty, go onto the next
            if line.strip() == '':
                continue

            # Deal with continuations by removing them to collapse
            # the lines together
            line_buffer += line
            if "&" in line_buffer:
                line_buffer = re.sub(r'&\s*\n', '', line_buffer)
                continue

            # Before output, minimise whitespace
            line_buffer = re.sub(r'\s+', r' ', line_buffer)
            yield line_buffer
            line_buffer = ''
