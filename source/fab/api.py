"""
This module allows any application to import all required
functions from fab to be imported independent of the location of the
files using `from fab.api import ...`.
"""

# TODO #518: allow versioned APIs, and make this file point to the
# current default API version.

from fab.artefacts import ArtefactSet, CollectionGetter
from fab.artefacts import SuffixFilter
from fab.build_config import AddFlags, BuildConfig
from fab.steps import run_mp
from fab.steps import step
from fab.steps.analyse import analyse
from fab.steps.archive_objects import archive_objects
from fab.steps.c_pragma_injector import c_pragma_injector
from fab.steps.cleanup_prebuilds import cleanup_prebuilds
from fab.steps.compile_c import compile_c
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import Exclude, find_source_files, Include
from fab.steps.grab.fcm import fcm_export
from fab.steps.grab.folder import grab_folder
from fab.steps.grab.git import git_checkout
from fab.steps.grab.prebuild import grab_pre_build
from fab.steps.link import link_exe, link_shared_object
from fab.steps.preprocess import preprocess_c, preprocess_fortran
from fab.steps.psyclone import preprocess_x90, psyclone
from fab.steps.root_inc_files import root_inc_files
from fab.tools.category import Category
from fab.tools.compiler import Compiler, Ifort
from fab.tools.compiler_wrapper import CompilerWrapper
from fab.tools.linker import Linker
from fab.tools.tool import Tool
from fab.tools.tool_box import ToolBox
from fab.tools.tool_repository import ToolRepository
from fab.util import common_arg_parser
from fab.util import file_checksum, log_or_dot, TimerLogger
from fab.util import get_fab_workspace
from fab.util import input_to_output_fpath

__all__ = [
    "AddFlags",
    "analyse",
    "archive_objects",
    "ArtefactSet",
    "BuildConfig",
    "Category",
    "cleanup_prebuilds",
    "CollectionGetter",
    "common_arg_parser",
    "Compiler",
    "CompilerWrapper",
    "compile_c",
    "compile_fortran",
    "c_pragma_injector",
    "Exclude",
    "fcm_export",
    "file_checksum",
    "get_fab_workspace",
    "git_checkout",
    "grab_folder",
    "grab_pre_build",
    "find_source_files",
    "Ifort",
    "Include",
    "input_to_output_fpath",
    "Linker",
    "link_exe",
    "link_shared_object",
    "log_or_dot",
    "preprocess_c",
    "preprocess_fortran",
    "preprocess_x90",
    "psyclone",
    "root_inc_files",
    "run_mp",
    "step",
    "SuffixFilter",
    "TimerLogger",
    "Tool",
    "ToolBox",
    "ToolRepository",
    ]
