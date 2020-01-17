# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution

'''
Source reading tools for Fortran format.
'''
import re


def sourcefile_iter(filename: str) -> str:
    '''
    Generator to return each line of a source file; the lines
    are sanitised to remove strings and comments, as well as
    collapsing the result of continuation lines and trimming
    away as much whitespace as possible
    '''
    with open(filename, 'r') as sourcefile:
        line_buffer = ''
        for line in sourcefile:
            # Remove strings - the pattern is designed so that it
            # remembers the opening quotation type and then matches
            # for its pair, ignoring any that are explicitly escaped
            line = re.sub(r'(\'|").*?(?<!\\)\1', r'\1\1', line)

            # Remove comments
            line = re.sub(r'!.*', '', line)

            # If the line is now empty, go onto the next
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
