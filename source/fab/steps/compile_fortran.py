##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fortran file compilation.

"""
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import List, Set, Dict

from fab.constants import COMPILED_FILES

from fab.metrics import send_metric

from fab.dep_tree import AnalysedFile
from fab.steps.mp_exe import MpExeStep
from fab.util import CompiledFile, log_or_dot_finish, log_or_dot, run_command, Timer, by_type, check_for_errors
from fab.artefacts import ArtefactsGetter, FilterBuildTrees

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.f90')


class CompileFortran(MpExeStep):

    def __init__(self, compiler: str = None, common_flags: List[str] = None, path_flags: List = None,
                 source: ArtefactsGetter = None, name='compile fortran'):
        compiler = compiler or os.getenv('FC', 'gfortran -c')
        super().__init__(exe=compiler, common_flags=common_flags, path_flags=path_flags, name=name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER

    def run(self, artefact_store, config):
        """
        Compiles all Fortran files in the *build_tree* artefact, creating the *compiled_fortran* artefact.

        This step uses multiprocessing, unless disabled in the :class:`~fab.steps.Step` class.

        """
        super().run(artefact_store, config)

        # get all the source to compile, for all build trees, into one big lump
        build_lists: Dict[str, List] = self.source_getter(artefact_store)
        to_compile = sum(build_lists.values(), [])
        logger.info(f"compiling {len(to_compile)} fortran files")

        # compile everything in multiple passes
        all_compiled: List[CompiledFile] = []  # todo: use set?
        already_compiled_files: Set[Path] = set([])  # a quick lookup

        per_pass = []
        while to_compile:

            compile_next = self.get_compile_next(already_compiled_files, to_compile)

            logger.info(f"\ncompiling {len(compile_next)} of {len(to_compile)} remaining files")
            results_this_pass = self.run_mp(items=compile_next, func=self.compile_file)
            check_for_errors(results_this_pass, caller_label=self.name)

            # check what we did compile
            compiled_this_pass: Set[CompiledFile] = set(by_type(results_this_pass, CompiledFile))
            per_pass.append(len(compiled_this_pass))
            if len(compiled_this_pass) == 0:
                logger.error("nothing compiled this pass")
                break

            # remove compiled files from list
            logger.debug(f"compiled {len(compiled_this_pass)} files")

            # results are not the same instances as passed in, due to mp copying
            compiled_fpaths = {i.analysed_file.fpath for i in compiled_this_pass}
            all_compiled.extend(compiled_this_pass)
            already_compiled_files.update(compiled_fpaths)

            # remove from remaining to compile
            to_compile = set(filter(lambda af: af.fpath not in compiled_fpaths, to_compile))

        log_or_dot_finish(logger)
        logger.debug(f"compiled per pass {per_pass}")
        logger.info(f"total fortran compiled {sum(per_pass)}")

        if to_compile:
            logger.debug(f"there were still {len(to_compile)} files left to compile")
            for af in to_compile:
                logger.debug(af.fpath)
            logger.error(f"there were still {len(to_compile)} files left to compile")
            exit(1)

        # add the targets' new object files to the artefact store
        lookup = {compiled_file.analysed_file: compiled_file for compiled_file in all_compiled}
        target_object_files = artefact_store.setdefault(COMPILED_FILES, defaultdict(set))
        for root, source_files in build_lists.items():
            new_objects = [lookup[af].output_fpath for af in source_files]
            target_object_files[root].update(new_objects)

    def get_compile_next(self, already_compiled_files: Set[Path], to_compile: List[AnalysedFile]):

        # find what to compile next
        compile_next = set()
        not_ready: Dict[Path, List[Path]] = {}
        for af in to_compile:
            # all deps ready?
            unfulfilled = [dep for dep in af.file_deps if dep not in already_compiled_files and dep.suffix == '.f90']
            if unfulfilled:
                not_ready[af.fpath] = unfulfilled
            else:
                compile_next.add(af)

        # unable to compile anything?
        if len(to_compile) and not compile_next:
            msg = 'Nothing more can be compiled due to unfulfilled dependencies:\n'
            for f, unf in not_ready.items():
                msg += f'\n\n{f}'
                for u in unf:
                    msg += f'\n    {str(u)}'

            raise RuntimeError(msg)

        return compile_next

    # todo: identical to the c version - make a super class
    def compile_file(self, analysed_file: AnalysedFile):
        output_fpath = analysed_file.fpath.with_suffix('.o')

        # already compiled?
        if self._config.reuse_artefacts and output_fpath.exists():
            log_or_dot(logger, f'CompileFortran skipping: {analysed_file.fpath}')
        else:
            with Timer() as timer:
                output_fpath.parent.mkdir(parents=True, exist_ok=True)

                command = self.exe.split()
                command.extend(self.flags.flags_for_path(
                    path=analysed_file.fpath,
                    source_root=self._config.source_root,
                    project_workspace=self._config.project_workspace))
                command.extend(os.getenv('FFLAGS', '').split())
                command.append(str(analysed_file.fpath))
                command.extend(['-o', str(output_fpath)])

                log_or_dot(logger, 'CompileFortran running command: ' + ' '.join(command))
                try:
                    run_command(command)
                except Exception as err:
                    return Exception("Error calling compiler:", err)

            send_metric(self.name, str(analysed_file.fpath), timer.taken)

        return CompiledFile(analysed_file, output_fpath)
