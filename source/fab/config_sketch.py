from collections import namedtuple
from typing import List, Optional, NamedTuple


class ConfigSketch(object):
    def __init__(self,
                 project_name,
                 grab_config,
                 extract_config,
                 cpp_flag_config,
                 fpp_flag_config,
                 fc_flag_config,
                 cc_flag_config,
                 root_symbol,
                 unreferenced_dependencies,
                 # ld_flags,
                 # output_filename,
                 linker,
                 special_measure_analysis_results=None):

        self.project_name = project_name
        self.grab_config = grab_config
        self.extract_config = extract_config
        self.cpp_flag_config = cpp_flag_config
        self.fpp_flag_config = fpp_flag_config
        self.fc_flag_config = fc_flag_config
        self.cc_flag_config = cc_flag_config
        self.root_symbol = root_symbol
        self.unreferenced_dependencies = unreferenced_dependencies
        # self.ld_flags = ld_flags
        # self.output_filename = output_filename
        self.linker = linker

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


class AddPathFlags(NamedTuple):
    flags: List[str]
    path_filter: str = ""


class FlagsConfig(object):
    """
    Return flags for a given path. Contains a list of PathFlags.

    Multiple path filters can match a given path.
    For now, simply allows appending flags but will likely evolve to replace or remove flags.

    """
    def __init__(self, common_flags=None, all_path_flags=None):
        self.common_flags: List[str] = common_flags or []
        self.all_path_flags: List[AddPathFlags] = all_path_flags or []

    def flags_for_path(self, path):
        flags_for_path = [*self.common_flags]
        for path_flags in self.all_path_flags:
            if not path_flags.path_filter or path_flags.path_filter in str(path):
                flags_for_path += path_flags.flags
        return flags_for_path


# def flags_from_file_system(path):
#     # we think we'll need sys admin config, possibly from the file system
#     pass
