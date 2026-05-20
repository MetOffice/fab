# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
A preprocessor and code generation step using PSyclone's transmute (Fortran to
Fortran) ability. .
https://github.com/stfc/PSyclone

"""
from dataclasses import dataclass
import logging
import shutil
import warnings
from itertools import chain
from pathlib import Path
from typing import Callable, cast, Optional, Sequence, Union


from fab.build_config import BuildConfig

from fab.artefacts import ArtefactSet
from fab.steps import run_mp, check_for_errors, step
from fab.tools.category import Category
from fab.tools.psyclone import Psyclone
from fab.util import (log_or_dot, input_to_output_fpath, file_checksum,
                      file_walk, TimerLogger, string_checksum,
                      by_type, log_or_dot_finish)

logger = logging.getLogger(__name__)


@dataclass
class MpCommonArgs:
    """
    Runtime data for child processes to read.

    Contains data used to calculate the prebuild hash.

    """
    config: BuildConfig
    suffix: str
    transformation_script: Optional[Callable[[Path, BuildConfig], Path]]
    cli_args: list[str]
    overrides_folder: Optional[Path]
    # filenames (not paths) of hand crafted overrides
    override_files: list[str]


@step
def psyclone_transmute(
        config: BuildConfig,
        fortran_files: Union[Sequence[Path], Sequence[Path]],
        transformation_script: Optional[Callable[[Path,
                                                  BuildConfig], Path]] = None,
        cli_args: Optional[list[str]] = None,
        suffix: Optional[str] = None,
        overrides_folder: Optional[Path] = None,
        artefact_set: Optional[ArtefactSet] = None,
        ):
    """
    PSyclone runner step.

    .. note::

        This step reads pre-processed Fortran files and produces replacement
        Fortran files. So it must be run before the
        :class:`~fab.steps.analyse.Analyse` step.

    This step stores results as prebuilds to speed up subsequent builds.
    To generate the prebuild hashes, it analyses the files, storing prebuilt
    results for these also.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read
        settings such as the project workspace folder or the multiprocessing
        flag.
    :param fortran_files: list of files to transform.
    :param transformation_script:
        The function to get Python transformation script.
        It takes in a file path and the config object, and returns the path
        of the transformation script or None. If no function is given or the
        function returns None, no script will be applied and PSyclone still
        runs.
    :param cli_args:
        Passed through to the psyclone cli tool.
    :param overrides_folder:
        Optional folder containing hand-crafted override files.
        Must be part of the subsequently analysed source code.
        Any file produced by psyclone will be deleted if there is a
        corresponding file in this folder.
    :param suffix: a suffix to be added to create the new filename.
    :param artefact_set: an optional artefact set. If specified, the
        input files names will be replaced with the newly transmuted ones.
    """

    if not suffix:
        suffix = "_transmute"

    cli_args = cli_args or []

    # get the data in a payload object for child processes to calculate
    # prebuild hashes
    mp_payload = _generate_mp_payload(config, overrides_folder,
                                      transformation_script, cli_args, suffix)

    config.prebuild_folder.mkdir(parents=True, exist_ok=True)

    # Run PSyclone. For every file, we get back a tuple of the output file and
    # the prebuild
    mp_arg = [(fortran_file, mp_payload) for fortran_file in fortran_files]
    with TimerLogger(f"running PSyclone transmute on {len(fortran_files)} "
                     f"Fortran files"):
        results = run_mp(config, mp_arg, transmute_one_file)
    log_or_dot_finish(logger)
    outputs, prebuilds = zip(*results) if results else ((), ())
    output_list = cast(list[str], outputs)
    prebuild_list = cast(list[str], prebuilds)
    check_for_errors(output_list, caller_label='psyclone')

    if artefact_set:
        config.artefact_store.replace(
            artefact_set,
            remove_files=fortran_files,
            add_files=output_list)

    # flatten the list of lists we got back from run_mp
    output_files: set[Path] = set(chain(*by_type(output_list, list)))
    prebuild_files: list[Path] = list(chain(*by_type(prebuild_list, list)))

    # record the output files in the artefact store for further processing
    config.artefact_store.add(ArtefactSet.FORTRAN_COMPILER_FILES, output_files)
    outputs_str = "\n".join(map(str, output_files))
    logger.debug(f'psyclone outputs:\n{outputs_str}\n')

    # Mark the prebuilds as being current so the
    # cleanup step doesn't delete them
    config.add_current_prebuilds(prebuild_files)
    prebuilds_str = "\n".join(map(str, prebuild_files))
    logger.debug(f'psyclone prebuilds:\n{prebuilds_str}\n')


def _generate_mp_payload(config,
                         overrides_folder,
                         transformation_script,
                         cli_args,
                         suffix: str) -> MpCommonArgs:
    override_files: list[str] = []
    if overrides_folder:
        override_files = [f.name for f in file_walk(overrides_folder)]

    return MpCommonArgs(
        config=config,
        transformation_script=transformation_script,
        cli_args=cli_args,
        overrides_folder=overrides_folder,
        override_files=override_files,
        suffix=suffix,
    )


def transmute_one_file(
        arg: tuple[Path, MpCommonArgs]) -> Union[tuple[Path, Path],
                                                 tuple[Exception, None]]:
    """
    Transmutes a single file. This function is called in parallel
    from psyclone_transmute.

    :param arg: all required data, stored in MpCommonArgs
    """
    input_file, mp_payload = arg
    config = mp_payload.config

    prebuild_hash = _gen_prebuild_hash(input_file,
                                       config,
                                       mp_payload.cli_args,
                                       mp_payload.transformation_script)

    # Create the output file name (with the suffix, and in the output
    # folder of Fab)
    output_file = input_to_output_fpath(config=config, input_path=input_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file = output_file.with_stem(output_file.stem + mp_payload.suffix)

    prebuild_out = (config.prebuild_folder /
                    f'{output_file.stem}.{prebuild_hash}{output_file.suffix}')

    # First check if we have an override file. If so, copy the override
    # file as the expected output file, and delete the prebuild file.
    if output_file.name in mp_payload.override_files:
        # Help mypy to know that overrides_folder is not None
        assert mp_payload.overrides_folder
        # there is an override so delete this output file...
        logger.warning(f"\nOverride found for '{output_file}'.")
        shutil.copy2(mp_payload.overrides_folder / output_file.name,
                     output_file)
        # Delete a prebuild, we do not want to store them
        prebuild_out.unlink(missing_ok=True)

    elif prebuild_out.exists():
        msg = f'Found prebuild for {input_file}: {prebuild_out}'
        log_or_dot(logger=logger, msg=msg)
        shutil.copy2(prebuild_out, output_file)
    else:
        psyclone = config.tool_box.get_tool(Category.PSYCLONE)
        psyclone = cast(Psyclone, psyclone)
        try:
            transformation_script = mp_payload.transformation_script
            logger.info(f"Running PSyclone on '{input_file}',"
                        f" creating '{output_file}'.")
            psyclone.process(config=mp_payload.config,
                             api=None,
                             x90_file=input_file,
                             transformed_file=output_file,
                             transformation_script=transformation_script,
                             additional_parameters=mp_payload.cli_args)

            shutil.copy2(output_file, prebuild_out)
            msg = f'Created prebuilds for {input_file}: {prebuild_out}'
            log_or_dot(logger=logger, msg=msg)

        except RuntimeError as err:
            logger.error(err)
            return err, None

    return output_file, prebuild_out


def _gen_prebuild_hash(input_file: Path,
                       config: BuildConfig,
                       cli_args: list[str],
                       script_func):
    """
    Calculate the prebuild hash for this Fortran input file, based on
    the source file and the transformation script.

    Changes which must trigger reprocessing of an x90 file:
     - input_file source:
     - transformation script
     - cli args

     :param input_file: Fortran input file.
     :param mp_payload: provides config file and command line args
    """

    input_hash = file_checksum(input_file).file_hash
    # calculate the transformation script hash for this file
    script_hash = 0
    if script_func:
        script = script_func(input_file, config)
        if script:
            script_hash = file_checksum(script).file_hash
    if script_hash == 0:
        # Only a warning. Running PSyclone without script can be used to
        # remove e.g. openmp directives (which PSyclone by default will do).
        warnings.warn(f'No transformation script specified for {input_file}.')

    # hash everything which should trigger re-processing
    # todo: hash the psyclone version?
    return sum([input_hash,
                string_checksum(str(cli_args)),
                script_hash])
