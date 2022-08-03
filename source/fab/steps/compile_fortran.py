##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fortran file compilation.

"""
import csv
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import List, Set, Dict, Optional

from fab.constants import OBJECT_FILES, BUILD_OUTPUT

from fab.metrics import send_metric

from fab.dep_tree import AnalysedFile
from fab.steps.mp_exe import MpExeStep
from fab.util import CompiledFile, log_or_dot_finish, log_or_dot, run_command, Timer, by_type, TimerLogger, \
    get_mod_hashes, string_checksum
from fab.steps import check_for_errors
from fab.artefacts import ArtefactsGetter, FilterBuildTrees

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.f90')

COMPILATION_CSV = "__fortran_compilation.csv"

# reasons to recompile, stored as constants for testability
NO_PREVIOUS_RESULT = 'no previous result'
SOURCE_CHANGED = 'source changed'
FLAGS_CHANGED = 'flags changed'
MODULE_DEPENDENCIES_CHANGED = 'module dependencies changed'
OBJECT_FILE_NOT_PRESENT = 'object file not present'
MODULE_FILE_NOT_PRESENT = 'module file(s) file not present'


class CompileFortran(MpExeStep):
    """
    Compiles all Fortran files in all build trees, creating or extending a set of compiled files for each target.

    This step uses multiprocessing.
    The files are compiled in multiple passes, with each pass enabling further files to be compiled in the next pass.

    """
    def __init__(self, compiler: str = None, common_flags: List[str] = None, path_flags: List = None,
                 source: ArtefactsGetter = None, name='compile fortran'):
        """
        :param compiler:
            The command line compiler to call. Defaults to `gfortran -c`.
        :param common_flags:
            A list of strings to be included in the command line call, for all files.
        :param path_flags:
            A list of :class:`~fab.build_config.AddFlags`, defining flags to be included in the command line call
            for selected files.
        :param source:
            An :class:`~fab.artefacts.ArtefactsGetter` which give us our c files to process.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        compiler = compiler or os.getenv('FC', 'gfortran -c')
        super().__init__(exe=compiler, common_flags=common_flags, path_flags=path_flags, name=name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER

        # runtime attributes for subprocess to read
        self._last_compiles: Dict[Path, CompiledFile] = {}
        self._mod_hashes: Dict[str, int] = {}

    def run(self, artefact_store, config):
        """
        Compile all Fortran files in all build trees.

        Uses multiprocessing, unless disabled in the *config*.

        :param artefact_store:
            Contains artefacts created by previous Steps, and where we add our new artefacts.
            This is where the given :class:`~fab.artefacts.ArtefactsGetter` finds the artefacts to process.
        :param config:
            The :class:`fab.build_config.BuildConfig` object where we can read settings
            such as the project workspace folder or the multiprocessing flag.

        """
        super().run(artefact_store, config)

        # read csv of last compile states
        self._last_compiles = self.read_compile_result(config)

        # get all the source to compile, for all build trees, into one big lump
        build_trees: Dict[str, List] = self.source_getter(artefact_store)

        # compile everything in multiple passes
        uncompiled: Set[AnalysedFile] = set(sum(build_trees.values(), []))
        logger.info(f"compiling {len(uncompiled)} fortran files")

        compiled: Dict[Path, CompiledFile] = {}
        while uncompiled:
            uncompiled = self.compile_pass(compiled, uncompiled, config)
        log_or_dot_finish(logger)

        self.write_compile_result(compiled, config)

        self.store_artefacts(compiled, build_trees, artefact_store)

    def compile_pass(self, compiled: Dict[Path, CompiledFile], uncompiled: Set[AnalysedFile], config):

        # what can we compile next?
        compile_next = self.get_compile_next(compiled, uncompiled)

        # compile
        logger.info(f"\ncompiling {len(compile_next)} of {len(uncompiled)} remaining files")
        results_this_pass = self.run_mp(items=compile_next, func=self.process_file)
        check_for_errors(results_this_pass, caller_label=self.name)
        compiled_this_pass = list(by_type(results_this_pass, CompiledFile))
        logger.debug(f"compiled {len(compiled_this_pass)} files")

        # hash the modules we just created
        new_mod_hashes = get_mod_hashes(compile_next, config)
        self._mod_hashes.update(new_mod_hashes)

        # add compiled files to all compiled files
        compiled.update({cf.input_fpath: cf for cf in compiled_this_pass})

        # remove compiled files from remaining files
        uncompiled = set(filter(lambda af: af.fpath not in compiled, uncompiled))
        return uncompiled

    def get_compile_next(self, compiled: Dict[Path, CompiledFile], uncompiled: Set[AnalysedFile]) -> Set[AnalysedFile]:

        # find what to compile next
        compile_next = set()
        not_ready: Dict[Path, List[Path]] = {}
        for af in uncompiled:
            # all deps ready?
            unfulfilled = [dep for dep in af.file_deps if dep not in compiled and dep.suffix == '.f90']
            if unfulfilled:
                not_ready[af.fpath] = unfulfilled
            else:
                compile_next.add(af)

        # unable to compile anything?
        if len(uncompiled) and not compile_next:
            msg = 'Nothing more can be compiled due to unfulfilled dependencies:\n'
            for f, unf in not_ready.items():
                msg += f'\n\n{f}'
                for u in unf:
                    msg += f'\n    {str(u)}'

            raise ValueError(msg)

        return compile_next

    def store_artefacts(self, compiled_files: Dict[Path, CompiledFile], build_trees: Dict[str, List], artefact_store):
        """
        Create our artefact collection; object files for each compiled file, per root symbol.

        """
        # add the targets' new object files to the artefact store
        lookup = {compiled_file.input_fpath: compiled_file for compiled_file in compiled_files.values()}
        object_files = artefact_store.setdefault(OBJECT_FILES, defaultdict(set))
        for root, source_files in build_trees.items():
            new_objects = [lookup[af.fpath].output_fpath for af in source_files]
            object_files[root].update(new_objects)

    # todo: identical to the c version - make a super class
    def process_file(self, analysed_file: AnalysedFile):
        """
        Prepare to compile a fortran file, and compile it if anything has changed since it was last compiled.

        Returns a compilation result, including various hashes from the time of compilation:

        * hash of the source file
        * hash of the compile flags
        * hash of the module files on which we depend

        """
        # flags for this file
        flags = self.flags.flags_for_path(
            path=analysed_file.fpath, source_root=self._config.source_root,
            project_workspace=self._config.project_workspace)
        flags_hash = string_checksum(str(flags))

        # do we need to recompile?
        last_compile = self._last_compiles.get(analysed_file.fpath)
        recompile_reasons = self.recompile_check(analysed_file, flags_hash, last_compile)

        if recompile_reasons:
            try:
                logger.debug(f'CompileFortran {recompile_reasons} for {analysed_file.fpath}')
                self.compile_file(analysed_file, flags)
            except Exception as err:
                return Exception("Error compiling file:", err)
        else:
            log_or_dot(logger, f'CompileFortran skipping: {analysed_file.fpath}')

        # get the hashes of the modules we depend on
        # record them so we know if they've changed next time we compile.
        try:
            module_deps_hashes = {mod_dep: self._mod_hashes[mod_dep] for mod_dep in analysed_file.module_deps}
        except KeyError:
            missing_mod_hashes = set(analysed_file.module_deps) - set(self._mod_hashes)
            return RuntimeError(f"Error compiling {analysed_file.fpath}: Missing module hash for {missing_mod_hashes}")

        return CompiledFile(
            input_fpath=analysed_file.fpath, output_fpath=analysed_file.fpath.with_suffix('.o'),
            source_hash=analysed_file.file_hash, flags_hash=flags_hash,
            module_deps_hashes=module_deps_hashes
        )

    def recompile_check(self, analysed_file: AnalysedFile, flags_hash: int, last_compile: Optional[CompiledFile]):

        # todo: other environmental considerations for the future:
        #   - env vars, e.g OMPI_FC
        #   - compiler version

        recompile_reasons = []
        # first encounter?
        if not last_compile:
            recompile_reasons.append(NO_PREVIOUS_RESULT)

        else:
            # source changed?
            if analysed_file.file_hash != last_compile.source_hash:
                recompile_reasons.append(SOURCE_CHANGED)

            # flags changed?
            if flags_hash != last_compile.flags_hash:
                recompile_reasons.append(FLAGS_CHANGED)

            # have any of the modules on which we depend changed?
            module_deps_hashes = {mod_dep: self._mod_hashes[mod_dep] for mod_dep in analysed_file.module_deps}
            if module_deps_hashes != last_compile.module_deps_hashes:
                recompile_reasons.append(MODULE_DEPENDENCIES_CHANGED)

            # is the object file still there?
            obj_file = analysed_file.fpath.with_suffix('.o')
            if not obj_file.exists():
                recompile_reasons.append(OBJECT_FILE_NOT_PRESENT)

            # are the module files we define still there?
            build_output = self._config.project_workspace / BUILD_OUTPUT
            mod_def_files = [build_output / f'{mod}.mod' for mod in analysed_file.module_defs]
            if not all([mod.exists() for mod in mod_def_files]):
                recompile_reasons.append(MODULE_FILE_NOT_PRESENT)

        return ", ".join(recompile_reasons)

    def compile_file(self, analysed_file, flags):
        with Timer() as timer:
            output_fpath = analysed_file.fpath.with_suffix('.o')
            output_fpath.parent.mkdir(parents=True, exist_ok=True)

            command = self.exe.split()
            command.extend(flags)
            command.extend(os.getenv('FFLAGS', '').split())
            command.append(str(analysed_file.fpath))
            command.extend(['-o', str(output_fpath)])

            log_or_dot(logger, 'CompileFortran running command: ' + ' '.join(command))
            run_command(command)

        send_metric(self.name, str(analysed_file.fpath), {'time_taken': timer.taken, 'start': timer.start})

    def write_compile_result(self, compiled: Dict[Path, CompiledFile], config):
        """
        Write the compilation results to csv.

        """
        compilation_progress_file = open(config.project_workspace / COMPILATION_CSV, "wt")
        dict_writer = csv.DictWriter(compilation_progress_file, fieldnames=CompiledFile.field_names())
        dict_writer.writeheader()

        for cf in compiled.values():
            dict_writer.writerow(cf.to_str_dict())

    def read_compile_result(self, config) -> Dict[Path, CompiledFile]:
        """
        Read the results of the last compile run.

        """
        with TimerLogger('loading compile results'):
            prev_results: Dict[Path, CompiledFile] = dict()
            try:
                with open(config.project_workspace / COMPILATION_CSV, "rt") as csv_file:
                    dict_reader = csv.DictReader(csv_file)
                    for row in dict_reader:
                        compiled_file = CompiledFile.from_str_dict(row)
                        prev_results[compiled_file.input_fpath] = compiled_file
            except FileNotFoundError:
                pass
            logger.info(f"loaded {len(prev_results)} compile results")

        return prev_results
