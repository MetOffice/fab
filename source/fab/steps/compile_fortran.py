import logging
from typing import List, Set

from fab.config_sketch import FlagsConfig
from fab.dep_tree import AnalysedFile, by_type

from fab.steps import Step
from fab.util import CompiledFile, log_or_dot_finish, log_or_dot, run_command

logger = logging.getLogger('fab')


class CompileFortran(Step):

    def __init__(self, compiler: List[str], flags: FlagsConfig, workspace, name='compile fortran', debug_skip=False):
        super().__init__(name)
        self._compiler = compiler
        self._flags = flags
        self._workspace = workspace
        self.debug_skip = debug_skip

    def run(self, artefacts):
        to_compile = {
            analysed_file for analysed_file in artefacts['build_tree'].values() if analysed_file.fpath.suffix == ".f90"}
        logger.info(f"\ncompiling {len(to_compile)} fortran files")

        all_compiled: List[CompiledFile] = []  # todo: use set?
        already_compiled_files = set()  # a quick lookup

        per_pass = []
        while to_compile:

            compile_next = self.get_compile_next(already_compiled_files, to_compile)

            logger.info(f"\ncompiling {len(compile_next)} of {len(to_compile)} remaining files")
            this_pass = self.run_mp(items=compile_next, func=self.compile_file)

            # any errors?
            # todo: improve by_type pattern to handle all exceptions as one
            errors = []
            for i in this_pass:
                if isinstance(i, Exception):
                    errors.append(i)
            if len(errors):
                logger.error(f"\nThere were {len(errors)} compile errors this pass\n\n")
            if errors:
                err_str = "\n\n".join(map(str, errors))
                logger.error(err_str)
                exit(1)  # todo: no exits

            # check what we did compile
            compiled_this_pass: Set[CompiledFile] = by_type(this_pass)[CompiledFile]
            per_pass.append(len(compiled_this_pass))
            if len(compiled_this_pass) == 0:
                logger.error("nothing compiled this pass")
                break

            # remove compiled files from list
            logger.debug(f"compiled {len(compiled_this_pass)} files")

            # ProgramUnit - not the same as passed in, due to mp copying
            compiled_fpaths = {i.analysed_file.fpath for i in compiled_this_pass}
            all_compiled.extend(compiled_this_pass)
            already_compiled_files.update(compiled_fpaths)

            # remove from remaining to compile
            to_compile = list(filter(lambda af: af.fpath not in compiled_fpaths, to_compile))

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

    def get_compile_next(self, already_compiled_files, to_compile):

        # find what to compile next
        compile_next = []
        not_ready = {}
        for af in to_compile:
            # all deps ready?
            unfulfilled = [dep for dep in af.file_deps if dep not in already_compiled_files and dep.suffix == '.f90']
            if not unfulfilled:
                compile_next.append(af)
            else:
                not_ready[af.fpath] = unfulfilled

        # unable to compile anything?
        if len(to_compile) and not compile_next:
            all_unfulfilled = set()
            for unfulfilled in not_ready.values():
                all_unfulfilled = all_unfulfilled.union(unfulfilled)
            logger.error(f"All unfulfilled deps: {', '.join(map(str, all_unfulfilled))}")
            exit(1)  # todo: no exits

        return compile_next

    def compile_file(self, analysed_file: AnalysedFile):
        command = [*self._compiler]
        command.extend(self._flags.flags_for_path(analysed_file.fpath))
        command.append(str(analysed_file.fpath))

        output_fpath = analysed_file.fpath.with_suffix('.o')
        if self.debug_skip and output_fpath.exists():
            log_or_dot(logger, f'Compiler skipping: {output_fpath}')
            return CompiledFile(analysed_file, output_fpath)

        command.extend(['-o', str(output_fpath)])

        log_or_dot(logger, 'Compiler running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            return Exception("Error calling compiler:", err)

        return CompiledFile(analysed_file, output_fpath)
