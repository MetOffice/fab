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
from typing import List, Set, Dict, Iterable

from fab.constants import OBJECT_FILES, BUILD_OUTPUT

from fab.metrics import send_metric

from fab.dep_tree import AnalysedFile
from fab.steps.mp_exe import MpExeStep
from fab.util import CompiledFile, log_or_dot_finish, log_or_dot, run_command, Timer, by_type, check_for_errors, \
    get_mod_hashes, TimerLogger, string_checksum
from fab.artefacts import ArtefactsGetter, FilterBuildTrees

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.f90')

COMPILATION_CSV = "__fortran_compilation.csv"


class CompileFortran(MpExeStep):

    def __init__(self, compiler: str = None, common_flags: List[str] = None, path_flags: List = None,
                 source: ArtefactsGetter = None, name='compile fortran'):
        compiler = compiler or os.getenv('FC', 'gfortran -c')
        super().__init__(exe=compiler, common_flags=common_flags, path_flags=path_flags, name=name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER

        # runtime
        self._last_compile: Dict[Path, CompiledFile] = {}
        self._mod_hashes: Dict[str, int] = {}

    def run(self, artefact_store, config):
        """
        Compile all Fortran files in all build trees.

        This step uses multiprocessing, unless disabled in the :class:`~fab.steps.Step` class.

        """
        super().run(artefact_store, config)

        # read csv of last compile states
        self._last_compile = self.read_compile_result()

        # mod hashes are made available to subprocesses for reading, and updated each pass with new mods
        self._mod_hashes = {}

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
        if len(compile_next) == 0:
            raise RuntimeError(f"Nothing can be compiled this pass. Needed to compile {uncompiled}")

        # compile
        logger.info(f"\ncompiling {len(compile_next)} of {len(uncompiled)} remaining files")
        results_this_pass = self.run_mp(items=compile_next, func=self.process_file)
        check_for_errors(results_this_pass, caller_label=self.name)
        compiled_this_pass: Set[CompiledFile] = set(by_type(results_this_pass, CompiledFile))
        logger.debug(f"compiled {len(compiled_this_pass)} files")

        # hash the modules we just created
        new_mod_hashes = get_mod_hashes(compile_next, config)
        self._mod_hashes.update(new_mod_hashes)

        # add compiled files to all compiled files
        compiled.update({cf.input_fpath: cf for cf in compiled_this_pass})

        # remove compiled files from remaining files
        uncompiled = set(filter(lambda af: af.fpath not in compiled, uncompiled))
        return uncompiled








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





    def compile_pass_old_DELETE_ME(self, compiled: Dict[Path, CompiledFile], uncompiled: List, config):

        # remove compiled from uncompiled
        uncompiled = set(filter(lambda af: af.fpath not in compiled, uncompiled))

        # what can we compile next?
        compile_next = self.get_compile_next(compiled, uncompiled)

        # compile
        logger.info(f"\ncompiling {len(compile_next)} of {len(uncompiled)} remaining files")
        results_this_pass = self.run_mp(items=compile_next, func=self.process_file)
        check_for_errors(results_this_pass, caller_label=self.name)

        # check what we compiled
        compiled_this_pass: Set[CompiledFile] = set(by_type(results_this_pass, CompiledFile))
        if len(compiled_this_pass) == 0:
            raise RuntimeError(f"Nothing compiled this pass. Needed to compile {compile_next}")
        logger.debug(f"compiled {len(compiled_this_pass)} files")

        # hash the modules we just created
        new_mod_hashes = get_mod_hashes(compile_next, config)
        self._mod_hashes.update(new_mod_hashes)

        # remove compiled files from list
        compiled.update({cf.input_fpath: cf for cf in compiled_this_pass})

        # remove from remaining to compile
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

            raise RuntimeError(msg)

        return compile_next

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
        last_compile = self._last_compile.get(analysed_file.fpath)
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

        send_metric(self.name, str(analysed_file.fpath), timer.taken)

    def recompile_check(self, analysed_file, flags_hash, last_compile):

        # todo: other environmental considerations for the future:
        #   - certain env vars, e.g OMPI_FC
        #   - compiler version

        recompile_reasons = []
        # first encounter?
        if not last_compile:
            recompile_reasons.append('no previous result')

        else:
            # source changed?
            if analysed_file.file_hash != last_compile.source_hash:
                recompile_reasons.append('source changed')

            # flags changed?
            if flags_hash != last_compile.flags_hash:
                recompile_reasons.append('flags changed')

            # have any of the modules on which we depend changed?
            module_deps_hashes = {mod_dep: self._mod_hashes[mod_dep] for mod_dep in analysed_file.module_deps}
            if module_deps_hashes != last_compile.module_deps_hashes:
                recompile_reasons.append('module dependencies changed')

            # is the object file still there?
            obj_file = analysed_file.fpath.with_suffix('.o')
            if not obj_file.exists():
                recompile_reasons.append('object file no longer present')

            # are the module files we define still there?
            build_output = self._config.project_workspace / BUILD_OUTPUT
            mod_def_files = [build_output / f'{mod}.mod' for mod in analysed_file.module_defs]
            if not all([mod.exists() for mod in mod_def_files]):
                recompile_reasons.append('module file(s) file no longer present')

        return ", ".join(recompile_reasons)

    def write_compile_result(self, compiled: Dict[Path, CompiledFile], config):
        """
        Write the compilation results to csv.

        """
        compilation_progress_file = open(self._config.project_workspace / COMPILATION_CSV, "wt")
        dict_writer = csv.DictWriter(compilation_progress_file, fieldnames=CompiledFile.field_names())
        dict_writer.writeheader()

        for cf in compiled.values():
            dict_writer.writerow(cf.to_str_dict())

        # compilation_progress_file.flush()
        # compilation_progress_file.close()

    def read_compile_result(self) -> Dict[Path, CompiledFile]:
        """
        Read the results of the last compile run.

        """
        with TimerLogger('loading compile results'):
            prev_results: Dict[Path, CompiledFile] = dict()
            try:
                with open(self._config.project_workspace / COMPILATION_CSV, "rt") as csv_file:
                    dict_reader = csv.DictReader(csv_file)
                    for row in dict_reader:
                        compiled_file = CompiledFile.from_str_dict(row)
                        prev_results[compiled_file.input_fpath] = compiled_file
            except FileNotFoundError:
                pass
            logger.info(f"loaded {len(prev_results)} compile results")

        return prev_results
