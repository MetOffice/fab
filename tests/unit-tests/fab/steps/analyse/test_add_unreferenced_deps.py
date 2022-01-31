from pathlib import Path

from fab.dep_tree import AnalysedFile

from fab.steps.analyse import Analyse


class Test_add_unreferenced_deps(object):

    def test_vanilla(self):

        analyser = Analyse()

        # we analysed the source folder and found these symbols
        symbols = {
            "root": Path("root.f90"),
            "root_dep": Path("root_dep.f90"),
            "util": Path("util.f90"),
            "util_dep": Path("util_dep.f90"),
        }

        # we extracted the build tree
        build_tree = {
            Path('root.f90'): AnalysedFile(fpath=Path(), file_hash=None),
            Path('root_dep.f90'): AnalysedFile(fpath=Path(), file_hash=None),
        }

        # we want to force this symbol into the build [because it's not used via modules]
        analyser.unreferenced_deps = ['util']

        # the stuff to add to the build tree will be found in here
        all_analysed_files = {
            # root.f90 and root_util.f90 would also be in here but the test doesn't need them
            Path('util.f90'): AnalysedFile(fpath=Path('util.f90'), file_deps={Path('util_dep.f90')}, file_hash=None),
            Path('util_dep.f90'): AnalysedFile(fpath=Path('util_dep.f90'), file_hash=None),
        }

        analyser._add_unreferenced_deps(symbols=symbols, all_analysed_files=all_analysed_files, build_tree=build_tree)

        assert Path('util.f90') in build_tree
        assert Path('util_dep.f90') in build_tree

    # todo:
    # def test_duplicate(self):
    #     # ensure warning
    #     pass
