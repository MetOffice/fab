from typing import Optional, List


class PathFlags(object):
    def __init__(self, action, path_filter=None):
        self.path_filter = path_filter or ""
        self.action = action

    def flags_for_path(self, path):
        if not self.path_filter or self.match_path(path):
            return self.action()

    def match_path(self, path):
        pass


def set_flags(flags):
    pass


def add_flags(flags):
    pass


def replace_flag(flag, val):
    raise NotImplementedError


#######


um_fpp_flags = PathFlags(
    action=set_flags("-DUM_JULES")
)


um_fc_flags = PathFlags(
    action=None
)


shum_fc_flags = PathFlags(
    path_filter="tmp-workspace/um/output/shumlib/",
    action=add_flags(['-std=f2018', '-c', '-J', workspace])
)

big_mem_flags = PathFlags(
    path_filter="big_mem_file.f90",
    action=add_flags(["--big-mem"])
)

force_flags = PathFlags(
    path_filter="foo",
    action=set_flags([])
)


fpp_flag_configs = [um_fpp_flags]
fc_flag_configs = [um_fc_flags, shum_fc_flags, big_mem_flags, force_flags]

#
# fc_flags = []
# for i in fc_flag_configs:
#     i.process(fc_flags)

