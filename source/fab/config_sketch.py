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


class PathFilter(object):
    def __init__(self, path_filters, include):
        self.path_filters = path_filters
        self.include = include

    def check(self, path):
        if any(i in str(path) for i in self.path_filters):
            return self.include
        return None


# class ReplaceFlags(object):
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
