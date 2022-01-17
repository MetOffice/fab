import warnings
from typing import List, Optional


class ConfigSketch(object):
    def __init__(self,
                 project_name,
                 grab_config,
                 extract_config,
                 cpp_flag_config,
                 fpp_flag_config,
                 fc_flag_config,
                 cc_flag_config,
                 ld_flags,
                 root_symbol,
                 unreferenced_dependencies,
                 output_filename,
                 special_measure_analysis_results=None):

        self.project_name = project_name
        self.grab_config = grab_config
        self.extract_config = extract_config
        self.cpp_flag_config = cpp_flag_config
        self.fpp_flag_config = fpp_flag_config
        self.fc_flag_config = fc_flag_config
        self.cc_flag_config = cc_flag_config
        self.ld_flags = ld_flags
        self.root_symbol = root_symbol
        self.unreferenced_dependencies = unreferenced_dependencies
        self.output_filename = output_filename

        # for when fparser2 cannot process a file but gfortran can compile it
        self.special_measure_analysis_results = special_measure_analysis_results

    #     # no target required when building a library.
    #     # if we supply one, it'll do dependency subtree extraction...
    #     if self.is_lib() and self.root_symbol:
    #         warnings.warn("Root symbol specified for library build. "
    #                       "Are you sure you need dependency subtree extraction?")
    #
    # def is_lib(self):
    #     return any(self.output_filename.endwith(i) for i in ['.so', '.a'])

    # todo: ?
    # def workspace(self):
    #     return WORKSPACE_ROOT / self.project_name


class PathFilter(object):
    def __init__(self, path_filters, include):
        self.path_filters = path_filters
        self.include = include

    def check(self, path):
        if any(i in str(path) for i in self.path_filters):
            return self.include
        return None


# class SetFlags(object):
#     """Overwrite"""
#     def __init__(self, flags):
#         self.flags = flags
#
#     def do(self, flags):
#         pass


# class AddFlags(object):
#     def __init__(self, flags):
#         self.flags = flags
#
#     def do(self, flags):
#         # todo: fail or warn if already exists?
#         pass


# def replace_flag(flag, val):
#     raise NotImplementedError


class PathFlags(object):
    """Flags for a path."""
    # todo: allow array of filters?

    def __init__(self, path_filter=None, add=None):
        self.path_filter = path_filter or ""
        self.add = add

    def do(self, path, flags_wip):
        if not self.add:
            return flags_wip

        if not self.path_filter or self.match_path(path):
            return flags_wip.extend(self.add)

    def match_path(self, path):
        return self.path_filter in str(path)


class FlagsConfig(object):
    """Flags for all the paths."""

    def __init__(self, path_flags: Optional[List[PathFlags]] = None):
        self.path_flags = path_flags or []

    def flags_for_path(self, path):
        flags_wip = []
        for i in self.path_flags:
            i.do(path, flags_wip)
        return flags_wip

# def flags_from_file_system(path):
#     # we think we'll need sys admin config, possibly from the file system
#     pass


#######

# def create_um_flags_config(workspace):
#
#     um_fpp_flags = PathFlags(
#         action=set_flags("-DUM_JULES")
#     )
#
#     um_fc_flags = PathFlags(
#         action=None
#     )
#
#     um_force_flags = PathFlags(
#         path_filter="foo",
#         action=set_flags([])
#     )
#
#     shum_fc_flags = PathFlags(
#         path_filter="tmp-workspace/um/output/shumlib/",
#         action=add_flags(['-std=f2018', '-c', '-J', workspace])
#     )
#
#     big_mem_flags = PathFlags(
#         path_filter="big_mem_file.f90",
#         action=add_flags(["--big-mem"])
#     )
#
#     sys_admin_forced_config = something_from_file_system("?")
#
#
#     fpp_config = FlagsConfig(path_flags=[um_fpp_flags])
#
#     fc_config = FlagsConfig(
#         path_flags=[um_fc_flags, shum_fc_flags, big_mem_flags, um_force_flags, sys_admin_forced_config]
#     )


# this is the line we need to use in the fortran compiler
# flags = fc_config.do(path)
