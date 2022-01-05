from typing import Optional


class PathMatcher(object):
    def __init__(self, patterns):
        self.patterns = patterns

    def check(self, path):
        pass


class PathFlags(object):
    def __init__(self, path_filter: Optional[PathMatcher], action):
        self.path_filter = path_filter
        self.action = action

    def flags_for_path(self, path):
        if not self.path_filter or self.path_filter.check(path):
            return self.action()


def set_flags(flags):
    pass


def add_flags(flags):
    pass


def replace_flag(flag, val):
    raise NotImplementedError


###


um_fpp_flags = PathFlags(
    path_filter=None,
    action=set_flags("-DUM_JULES")
)


um_fc_flags = PathFlags(
    path_filter=None,
    action=None
)


f2018_files = PathMatcher(
    patterns=[
        "/home/h02/bblay/git/fab/tmp-workspace/um/output/shumlib",
    ],
)


shum_fc_flags = PathFlags(
    path_filter=f2018_files,
    action=add_flags(['-std=f2018', '-c', '-J', workspace])
)


fpp_flag_configs = [um_fpp_flags]
fc_flag_configs = [um_fc_flags, shum_fc_flags]

