"""
This module allows any application to import all required
functions from fab to be imported independent of the location of the
files using `from fab.api import ...`.
"""

from fab.artefacts import ArtefactSet, CollectionGetter, SuffixFilter
from fab.build_config import AddFlags, BuildConfig
from fab.fab_base.fab_base import FabBase
from fab.steps import run_mp, step
from fab.steps.analyse import analyse
from fab.steps.archive_objects import archive_objects
from fab.steps.c_pragma_injector import c_pragma_injector
from fab.steps.cleanup_prebuilds import cleanup_prebuilds
from fab.steps.compile_c import compile_c
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import Exclude, Include, find_source_files
from fab.steps.grab.dependency_info import DependencyInfo
from fab.steps.grab.fcm import fcm_export
from fab.steps.grab.files import grab_files
from fab.steps.grab.folder import grab_folder
from fab.steps.grab.git import git_checkout
from fab.steps.grab.prebuild import grab_pre_build
from fab.steps.link import link_exe, link_shared_object
from fab.steps.preprocess import preprocess_c, preprocess_fortran
from fab.steps.psyclone import preprocess_x90, psyclone
from fab.steps.psyclone_transmute import psyclone_transmute
from fab.steps.root_inc_files import root_inc_files
from fab.tools.category import Category
from fab.tools.compiler import Compiler, Ifort
from fab.tools.compiler_wrapper import CompilerWrapper
from fab.tools.flags import AlwaysFlags, ContainFlags, FlagList, MatchFlags
from fab.tools.linker import Linker
from fab.tools.pkg_config import PkgConfig
from fab.tools.preprocessor import Cpp, Fpp
from fab.tools.profile_flags import ProfileFlags
from fab.tools.shell import Shell
from fab.tools.tool import Tool
from fab.tools.tool_box import ToolBox
from fab.tools.tool_repository import ToolRepository
from fab.util import (
    TimerLogger,
    common_arg_parser,
    file_checksum,
    get_fab_workspace,
    input_to_output_fpath,
    log_or_dot,
)

__all__ = [
    "AddFlags",
    "AlwaysFlags",
    "ArtefactSet",
    "BuildConfig",
    "Category",
    "CollectionGetter",
    "Compiler",
    "CompilerWrapper",
    "ContainFlags",
    "Cpp",
    "DependencyInfo",
    "Exclude",
    "FabBase",
    "FlagList",
    "Fpp",
    "Ifort",
    "Include",
    "Linker",
    "MatchFlags",
    "PkgConfig",
    "ProfileFlags",
    "Shell",
    "SuffixFilter",
    "TimerLogger",
    "Tool",
    "ToolBox",
    "ToolRepository",
    "analyse",
    "archive_objects",
    "c_pragma_injector",
    "cleanup_prebuilds",
    "common_arg_parser",
    "compile_c",
    "compile_fortran",
    "fcm_export",
    "file_checksum",
    "find_source_files",
    "get_fab_workspace",
    "git_checkout",
    "grab_files",
    "grab_folder",
    "grab_pre_build",
    "input_to_output_fpath",
    "link_exe",
    "link_shared_object",
    "log_or_dot",
    "preprocess_c",
    "preprocess_fortran",
    "preprocess_x90",
    "psyclone",
    "psyclone_transmute",
    "root_inc_files",
    "run_mp",
    "step",
]
