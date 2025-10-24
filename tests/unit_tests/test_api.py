##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Tests the API submodule. It will also test the API numbered profile,
which atm is v1 (i.e. fab.api and fab.v1 will export the same symbols).
"""

from importlib import import_module
from pytest import fail


def test_import_from_api() -> None:
    """
    Test that we can import the specified symbol from fab.api.
    """

    all_symbols = [
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

    fab_api = import_module("fab.api")
    for symbol_name in all_symbols:
        try:
            symbol = getattr(fab_api, symbol_name)
            assert symbol.__name__ == symbol_name
        except AttributeError:
            fail(f"Symbol `{symbol_name}` could not be imported "
                 f"from `fab.api`.")
