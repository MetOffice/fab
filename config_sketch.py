from typing import List, Optional


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
    def __init__(self, add=None, path_filter=None):
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

