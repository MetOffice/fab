##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Add custom pragmas to C code which identify user and system include regions.

"""
import re
from pathlib import Path
from typing import Pattern, Optional, Match

from fab import FabException
from fab.constants import PRAGMAD_C
from fab.steps import run_mp, step
from fab.artefacts import ArtefactsGetter, SuffixFilter

DEFAULT_SOURCE_GETTER = SuffixFilter('all_source', '.c')


# todo: test
@step
def c_pragma_injector(config, source: Optional[ArtefactsGetter] = None, output_name=None):
    """
    A build step to inject custom pragmas to mark blocks of user and system include statements.

    By default, reads .c files from the *all_source* artefact and creates the *pragmad_c* artefact.

    This step does not write to the build output folder, it creates the pragmad c in the same folder as the c file.
    This is because a subsequent preprocessing step needs to look in the source folder for header files,
    including in paths relative to the c file.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read settings
        such as the project workspace folder or the multiprocessing flag.
    :param source:
        An :class:`~fab.artefacts.ArtefactsGetter` which give us our c files to process.
    :param output_name:
        The name of the artefact collection to create in the artefact store, with a sensible default

    """
    source_getter = source or DEFAULT_SOURCE_GETTER
    output_name = output_name or PRAGMAD_C

    files = source_getter(config.artefact_store)
    results = run_mp(config, items=files, func=_process_artefact)
    config.artefact_store[output_name] = list(results)


def _process_artefact(fpath: Path):
    prag_output_fpath = fpath.with_suffix('.prag')
    prag_output_fpath.open('w').writelines(inject_pragmas(fpath))
    return prag_output_fpath


def inject_pragmas(fpath):
    """
    Reads a C source file but when encountering an #include
    preprocessor directive injects a special Fab-specific
    #pragma which can be picked up later by the Analyser
    after the preprocessing
    """

    _include_re: str = r'^\s*#include\s+(\S+)'
    _include_pattern: Pattern = re.compile(_include_re)

    for line in open(fpath, 'rt', encoding='utf-8'):
        include_match: Optional[Match] = _include_pattern.match(line)
        if include_match:
            # For valid C the first character of the matched
            # part of the group will indicate whether this is
            # a system library include or a user include
            include: str = include_match.group(1)
            if include.startswith('<'):
                yield '#pragma FAB SysIncludeStart\n'
                yield line
                yield '#pragma FAB SysIncludeEnd\n'
            elif include.startswith(('"', "'")):
                yield '#pragma FAB UsrIncludeStart\n'
                yield line
                yield '#pragma FAB UsrIncludeEnd\n'
            else:
                msg = 'Found badly formatted #include'
                raise FabException(msg)
        else:
            yield line
