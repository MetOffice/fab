#!/usr/bin/env python3

'''
This module contains a class that reads in fcm extract specifications.
'''


from pathlib import Path
import re
import sys


class FcmExtract(dict):
    '''
    A simple class that reads in an fcm extract.cfg file and stores
    the information about excluded and included file to be used in FAB.

    :param str filename: the name of the fcm extract file to read.
    '''

    def __init__(self, filename):
        # pylint: disable=too-many-branches, too-many-statements
        # pylint: disable=too-many-locals
        super().__init__()
        re_comment = re.compile(r"( *#.*$)")
        re_include = re.compile(r"^ *include", re.I)
        re_location = re.compile(r"^ *extract.location\{diff\}\[.*\] *=")
        re_files = re.compile(r"^ *(.*)_extract_files.* *= *(.*) *$")
        re_excl = re.compile(r"^ *extract\.path-excl\[(.*)\] *= *(.*) *$")
        re_incl = re.compile(r"^ *extract\.path-incl\[(.*)\] *= *(.*) *$")

        # Read the files, remove comments and empty lines, and handle '\'
        with open(filename, encoding="utf8") as f_in:
            current_line = []
            for line in f_in:
                line = line.strip()
                comm = re_comment.search(line)
                if comm:
                    # Remove comments
                    line = line[:comm.start()].strip()
                # Handle multi-line
                if line.endswith("\\"):
                    current_line.append(line[:-1].strip())
                    continue

                current_line.append(line)
                line = " ".join(current_line)
                current_line = []
                if not line:
                    continue
                if not line or re_include.match(line):
                    # Includes are not supported
                    print(f"Ignoring include '{line}'.")
                    continue
                if re_location.match(line):
                    # Ignore location info
                    continue
                grp = re_files.match(line)
                if grp:
                    section = grp.group(1).lower()
                    list_of_paths = [Path(i) for i in grp.group(2).split(" ")]
                    if section in self:
                        self[section].append(("include", list_of_paths))
                    else:
                        self[section] = [("include", list_of_paths)]
                    continue
                grp = re_excl.match(line)
                if grp:
                    line_type = "exclude"
                else:
                    grp = re_incl.match(line)
                    line_type = "include"
                if not grp:
                    print(f"Unexpected line: '{line}' - ignored.")
                    continue
                section = grp.group(1).lower()
                list_of_paths = [Path(i) for i in grp.group(2).split(" ")]
                if section in self:
                    self[section].append((line_type, list_of_paths))
                else:
                    self[section] = [(line_type, list_of_paths)]


# ============================================================================
def main():
    '''
    Simple wrapper to avoid pylint errors.
    '''
    fe = FcmExtract(sys.argv[1])
    print("Sections", fe.keys())
    for section, list_of_paths in fe.items():
        print("SECTION:", section, list_of_paths)


# ============================================================================
if __name__ == "__main__":
    # Avoid pylint errors about redefinition from outer scope
    main()
