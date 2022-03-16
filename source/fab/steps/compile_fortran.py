##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fortran file compilation.

"""
import logging
from pathlib import Path
from typing import List, Set, Dict

from fab.dep_tree import AnalysedFile, by_type
from fab.steps.mp_exe import MpExeStep
from fab.util import CompiledFile, log_or_dot_finish, log_or_dot, run_command, FilterBuildTree, SourceGetter

logger = logging.getLogger('fab')

DEFAULT_SOURCE_GETTER = FilterBuildTree(suffixes=['.f90'])


class CompileFortran(MpExeStep):

    def __init__(self, compiler: str, common_flags: List[str] = None, path_flags: List = None,
                 source: SourceGetter = None, name='compile fortran'):
        super().__init__(exe=compiler, common_flags=common_flags, path_flags=path_flags, name=name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER

    def run(self, artefacts, config):
        """
        Compiles all Fortran files in the *build_tree* artefact, creating the *compiled_fortran* artefact.

        This step uses multiprocessing, unless disabled in the :class:`~fab.steps.Step` class.

        """
        super().run(artefacts, config)

        to_compile = self.source_getter(artefacts)
        logger.info(f"\ncompiling {len(to_compile)} fortran files")

        all_compiled: List[CompiledFile] = []  # todo: use set?
        already_compiled_files: Set[Path] = set([])  # a quick lookup

        per_pass = []
        while to_compile:

            compile_next = self.get_compile_next(already_compiled_files, to_compile)

            logger.info(f"\ncompiling {len(compile_next)} of {len(to_compile)} remaining files")
            results_this_pass = self.run_mp(items=compile_next, func=self.compile_file)

            # any errors?
            errors = list(by_type(results_this_pass, Exception))
            if len(errors):
                logger.error(f"\nThere were {len(errors)} compile errors this pass\n\n")
            if errors:
                err_str = "\n\n".join(map(str, errors))
                raise RuntimeError(f"Error in compiling pass: {err_str}")

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

        artefacts['compiled_fortran'] = all_compiled

    def get_compile_next(self, already_compiled_files: Set[Path], to_compile: Set[AnalysedFile]):

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
            all_unfulfilled: Set[Path] = set()
            for unfulfilled in not_ready.values():
                all_unfulfilled = all_unfulfilled.union(unfulfilled)
            raise RuntimeError(
                f"Nothing more can be compiled due to unfulfilled dependencies: {', '.join(map(str, all_unfulfilled))}")

        return compile_next

    def compile_file(self, analysed_file: AnalysedFile):
        command = [self.exe]
        command.extend(self.flags.flags_for_path(analysed_file.fpath, self._config.workspace))
        command.append(str(analysed_file.fpath))

        output_fpath = analysed_file.fpath.with_suffix('.o')
        if self._config.debug_skip and output_fpath.exists():
            log_or_dot(logger, f'Compiler skipping: {output_fpath}')
            return CompiledFile(analysed_file, output_fpath)

        command.extend(['-o', str(output_fpath)])

        log_or_dot(logger, 'Compiler running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            return Exception("Error calling compiler:", err)

        return CompiledFile(analysed_file, output_fpath)
