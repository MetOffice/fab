# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from fparser.common.readfortran import FortranFileReader
from fparser.two.parser import ParserFactory


def do(fpath, f2008_parser):

    reader = FortranFileReader(fpath, ignore_comments=False)
    reader.exit_on_error = False  # don't call sys.exit, it messes up the multi-processing
    tree = f2008_parser(reader)
    return tree


if __name__ == '__main__':
    f2008_parser = ParserFactory().create(std="f2008")

    do('/var/tmp/persistent/fab_workspace/master_gungho_gfortran_Og_1stage/build_output/solver/iterative_solver_mod.f90', f2008_parser)
    do('/var/tmp/persistent/fab_workspace/inc_psyc_gungho_gfortran_Og_1stage/build_output/solver/iterative_solver_mod.f90', f2008_parser)
    do('/tmp/persistent/fab_workspace/inc_psyc_gungho_gfortran_Og_1stage/build_output/solver/iterative_solver_mod.f90', f2008_parser)
