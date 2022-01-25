import logging
from pathlib import PosixPath, Path

from fab.constants import BUILD_SOURCE

from fab.config_sketch import FlagsConfig
from fab.dep_tree import by_type

from fab.steps import Step
from fab.tasks.c import _CTextReaderPragmas
from fab.util import log_or_dot_finish, input_to_output_fpath, fixup_command_includes, log_or_dot, run_command

logger = logging.getLogger('fab')


class PreProcessor(Step):
    """
    A build step which calls a preprocessor. Used for both C and Fortran.

    """

    def __init__(self,
                 flags: FlagsConfig,
                 workspace: Path,
                 name='preprocess',
                 preprocessor='cpp',
                 debug_skip=False,
                 ):
        """
        Args:
            - flags: Config object defining common and per-path flags.
            - workspace: The folder in which to find the source and output folders.

        Kwargs:
            - preprocessor: The name of the executable. Defaults to 'cpp'.
            - debug_skip: Ignore this for now!

        """
        super().__init__(name=name)

        self._preprocessor = preprocessor
        self._flags = flags
        self._workspace = workspace
        self.debug_skip = debug_skip

    # def input_artefacts(self, artefacts):
    #     raise NotImplementedError
    #
    # def output_artefacts(self, results, artefacts):
    #     raise NotImplementedError

    def process_artefact(self, fpath):
        """
        Expects an input file in the source folder.
        Writes the output file to the output folder, with a lower case extension.

        """
        output_fpath = input_to_output_fpath(workspace=self._workspace, input_path=fpath)

        if fpath.suffix == ".c":
            # pragma injection
            # todo: The .prag file should probably live in the output folder.
            prag_output_fpath = fpath.parent / (fpath.name + ".prag")
            prag_output_fpath.open('w').writelines(_CTextReaderPragmas(fpath))
            input_fpath = prag_output_fpath
        elif fpath.suffix in [".f90", ".F90"]:
            input_fpath = fpath
            output_fpath = output_fpath.with_suffix('.f90')
        else:
            raise ValueError(f"Unexpected file type: '{str(fpath)}'")

        # for dev speed, but this could become a good time saver with, e.g, hashes or something
        if self.debug_skip and output_fpath.exists():
            log_or_dot(logger, f'Preprocessor skipping: {fpath}')
            return output_fpath

        if not output_fpath.parent.exists():
            output_fpath.parent.mkdir(parents=True, exist_ok=True)

        command = [self._preprocessor]
        command.extend(self._flags.flags_for_path(fpath))

        # the flags we were given might contain include folders which need to be converted into absolute paths
        # todo: inconsistent with the compiler (and c?), which doesn't do this - discuss
        command = fixup_command_includes(command=command, source_root=self._workspace / BUILD_SOURCE, file_path=fpath)

        # input and output files
        command.append(str(input_fpath))
        command.append(str(output_fpath))

        log_or_dot(logger, 'PreProcessor running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error preprocessing {fpath}: {err}")

        return output_fpath


class FortranPreProcessor(PreProcessor):

    def run(self, artefacts):

        mp_input = artefacts['all_source']['.f90'] + artefacts['all_source']['.F90']

        results = self.run_mp(artefacts=mp_input, func=self.process_artefact)

        # todo: move into run_mp?
        results_by_type = by_type(results)

        # any errors?
        if results_by_type[Exception]:
            formatted_errors = "\n\n".join(map(str, results_by_type[Exception]))
            raise Exception(
                f"{formatted_errors}"
                f"\n\n{len(results_by_type[Exception])} "
                f"Error(s) found during preprocessing: "
            )

        log_or_dot_finish(logger)

        artefacts['preprocessed_fortran'] = results_by_type[PosixPath]


class CPreProcessor(PreProcessor):

    def run(self, artefacts):
        mp_input = artefacts['all_source']['.c']

        results = self.run_mp(artefacts=mp_input, func=self.process_artefact)

        # todo: move into run_mp?
        results_by_type = by_type(results)

        # any errors?
        if results_by_type[Exception]:
            formatted_errors = "\n\n".join(map(str, results_by_type[Exception]))
            raise Exception(
                f"{formatted_errors}"
                f"\n\n{len(results_by_type[Exception])} "
                f"Error(s) found during preprocessing: "
            )

        log_or_dot_finish(logger)

        artefacts['preprocessed_c'] = results_by_type[PosixPath]
