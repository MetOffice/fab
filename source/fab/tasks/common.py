# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution

import logging
import subprocess
from typing import List, Set
from pathlib import Path

from fab.util import CompiledFile


class Linker(object):
    def __init__(self, linker: str, flags: List[str], workspace: Path, output_filename: str):
        self._linker = linker
        self._flags = flags
        self._workspace = workspace
        self._output_filename = output_filename

    def run(self, compiled_files: Set[CompiledFile]):
        logger = logging.getLogger(__name__)
        output_file = str(self._workspace / self._output_filename)

        # building a library?
        # shared object
        # todo: refactor this
        # TODO: WE PROBABLY WANT TO BUILD A .a FILE WITH ar INSTEAD OF A SHARED OBJECT - DISCUSS
        if self._output_filename.endswith('.so'):
            command = ['gcc', '-fPIC', '-shared', '-o', output_file]
            command.extend([str(a.output_fpath) for a in compiled_files])

        if self._output_filename.endswith('.a'):
            command = ['ar', 'cr', output_file]
            command.extend([str(a.output_fpath) for a in compiled_files])

        # building an executable
        else:
            command = [self._linker]
            command.extend(['-o', str(output_file)])
            for compiled_file in compiled_files:
                command.append(str(compiled_file.output_fpath))
            command.extend(self._flags)

        logger.debug('Running command: ' + ' '.join(command))

        try:
            res = subprocess.run(command, check=True)
            if res.returncode != 0:
                # todo: specific exception
                raise Exception(f"The command exited with non zero: {res.stderr.decode()}")
        except Exception as err:
            raise Exception(f"error: {err}")

        return self._output_filename

