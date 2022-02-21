
Fab Overview
============

Use Fab to build your Fortran and C project using a series of build steps.

You can configure the list of build steps, configure the steps themselves
and create your own custom build steps.

Fab analyses your code to determine dependencies, including those between C and Fortran.
It can work out which files need to be compiled to create an executable,
or build all your source into a static or shared library.

Example config::

    workspace = Path('my_workspace')

    config = Config(label='my fab build', workspace=workspace)

    config.steps = [
        GetSourceFiles(workspace / 'source'),
        CPreProcessor(),
        FortranPreProcessor(
            common_flags=['-traditional-cpp', '-P',
                '-I', '$source/gcom/include',
                '-DGC_VERSION="7.6"'],
        ),
        Analyse(root_symbol='my_program'),
        CompileC(common_flags=['-c', '-std=c99']),
        CompileFortran(compiler='gfortran', common_flags=['-c', '-J', '$output']),
        LinkExe(
            linker='gcc',
            flags=['-lc', '-lgfortran', '-L', 'lib', '-l', 'libmylib'],
            output_fpath='my_program.exe')
    ]


Fab Developer Overview
======================
Build steps are derived from the Step class and usually create artefacts.

Fab runs each step in order, passing in all the artefacts from previous steps,
plus all the config.

Steps have access to multiprocessing methods. The MpExeStep class captures common aspects
of steps which pass a list of artefacts through a commandline tool.