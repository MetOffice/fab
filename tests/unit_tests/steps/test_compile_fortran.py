from pathlib import Path
from typing import Dict
from unittest.mock import Mock

from pyfakefs.fake_filesystem import FakeFilesystem
from pytest import fixture, mark, raises, warns
from pytest_subprocess.fake_process import FakeProcess

from fab.artefacts import ArtefactSet, ArtefactStore
from fab.build_config import BuildConfig, FlagsConfig
from fab.parse.fortran import AnalysedFortran
from fab.steps.compile_fortran import (
    compile_pass, get_compile_next,
    get_mod_hashes, handle_compiler_args, MpCommonArgs, process_file,
    store_artefacts
)
from fab.tools.category import Category
from fab.tools.tool_box import ToolBox
from fab.util import CompiledFile


@fixture(scope='function')
def analysed_files():
    a = AnalysedFortran(fpath=Path('/fab/a.f90'),
                        file_deps={Path('/fab/b.f90')},
                        file_hash=0)
    b = AnalysedFortran(fpath=Path('/fab/b.f90'),
                        file_deps={Path('/fab/c.f90')},
                        file_hash=0)
    c = AnalysedFortran(fpath=Path('/fab/c.f90'), file_hash=0)
    return a, b, c


@fixture(scope='function')
def artefact_store(analysed_files):
    build_tree = {af.fpath: af for af in analysed_files}
    artefact_store = {ArtefactSet.BUILD_TREES: {None: build_tree}}
    return artefact_store


def test_compile_cc_wrong_compiler(stub_tool_box,
                                   fs: FakeFilesystem,
                                   fake_process: FakeProcess) -> None:
    """
    Tests specifying the wrong compiler causes an error.

    ToDo: Is this a thing which can ever happen?
    """
    config = BuildConfig('proj', stub_tool_box, mpi=False, openmp=False)
    # Get the default Fortran compiler into the ToolBox
    fc = stub_tool_box.get_tool(Category.FORTRAN_COMPILER)
    # But then change its category to be a C compiler:
    #
    # ToDo: Monkeying with private state is bad.
    #
    fc._category = Category.C_COMPILER

    # Now check that _compile_file detects the incorrect category of the
    # Fortran compiler
    mp_common_args = Mock(config=config)
    with raises(RuntimeError) as err:
        process_file((Mock(), mp_common_args))
    assert str(err.value) \
           == "Unexpected tool 'some Fortran compiler' of category " \
              + "'C_COMPILER' instead of FortranCompiler"

    with raises(RuntimeError) as err:
        handle_compiler_args(config)
    assert str(err.value) \
        == "Unexpected tool 'some Fortran compiler' of category " \
           + "'C_COMPILER' instead of FortranCompiler"


class TestCompilePass:

    def test_vanilla(self, analysed_files, stub_tool_box: ToolBox,
                     tmp_path: Path, fake_process: FakeProcess) -> None:
        """
        Tests only uncompiled artefacts are compiled.

        This test uses a real filesystem as it seems that multiprocessing
        doesn't work will with the fake one.
        """
        a, b, c = analysed_files

        fake_process.register(['sfc', '--version'], stdout='1.2.3')
        fake_process.register(['sfc', fake_process.any()])

        uncompiled = {a, b}
        compiled = {
            c.fpath: CompiledFile(c.fpath,
                                  tmp_path / 'proj/build_output/_prebuild/' / c.fpath.name)
        }

        # this gets filled in
        mod_hashes: Dict[str, int] = {}

        config = BuildConfig('proj', stub_tool_box, fab_workspace=tmp_path)
        mp_common_args = MpCommonArgs(config,
                                      FlagsConfig(),
                                      {},
                                      syntax_only=True)
        uncompiled_result = compile_pass(config=config,
                                         compiled=compiled,
                                         uncompiled=uncompiled,
                                         mod_hashes=mod_hashes,
                                         mp_common_args=mp_common_args)

        assert Path('/fab/a.f90') not in compiled
        assert Path('/fab/b.f90') in compiled
        assert list(uncompiled_result)[0].fpath == Path('/fab/a.f90')


class TestGetCompileNext:

    def test_vanilla(self, analysed_files):
        a, b, c = analysed_files
        uncompiled = {a, b}
        compiled = {c.fpath: Mock(input_fpath=c.fpath)}

        compile_next = get_compile_next(compiled, uncompiled)

        assert compile_next == {b}

    def test_unable_to_compile_anything(self, analysed_files):
        # like vanilla, except c hasn't been compiled
        a, b, _ = analysed_files
        to_compile = {a, b}
        already_compiled_files = {}

        with raises(ValueError):
            get_compile_next(already_compiled_files, to_compile)


class TestStoreArtefacts:

    def test_vanilla(self):

        # what we wanted to compile
        build_lists = {
            'root1': [
                Mock(fpath=Path('root1.f90')),
                Mock(fpath=Path('dep1.f90')),
            ],
            'root2': [
                Mock(fpath=Path('root2.f90')),
                Mock(fpath=Path('dep2.f90')),
            ],
        }

        # what we actually compiled
        compiled_files = {
            Path('root1.f90'): Mock(input_fpath=Path('root1.f90'), output_fpath=Path('root1.o')),
            Path('dep1.f90'): Mock(input_fpath=Path('dep1.f90'), output_fpath=Path('dep1.o')),
            Path('root2.f90'): Mock(input_fpath=Path('root2.f90'), output_fpath=Path('root2.o')),
            Path('dep2.f90'): Mock(input_fpath=Path('dep2.f90'), output_fpath=Path('dep2.o')),
        }

        # where it stores the results
        artefact_store = ArtefactStore()

        store_artefacts(compiled_files=compiled_files, build_lists=build_lists,
                        artefact_store=artefact_store)

        assert artefact_store[ArtefactSet.OBJECT_FILES] == {
                'root1': {Path('root1.o'), Path('dep1.o')},
                'root2': {Path('root2.o'), Path('dep2.o')},
            }


# This avoids pylint warnings about Redefining names from outer scope
@fixture(scope='function')
def content(stub_tool_box, fs: FakeFilesystem):
    flags = ['flag1', 'flag2']
    flags_config = Mock()
    flags_config.flags_for_path.return_value = flags

    analysed_file = AnalysedFortran(fpath=Path('foofile'), file_hash=34567)
    analysed_file.add_module_dep('mod_dep_1')
    analysed_file.add_module_dep('mod_dep_2')
    analysed_file.add_module_def('mod_def_1')
    analysed_file.add_module_def('mod_def_2')

    mp_common_args = MpCommonArgs(
        config=BuildConfig('proj', stub_tool_box, fab_workspace=Path('/fab')),
        flags=flags_config,
        mod_hashes={'mod_dep_1': 12345, 'mod_dep_2': 23456},
        syntax_only=False,
    )

    return (mp_common_args, flags, analysed_file)


class TestProcessFile:
    def test_without_prebuild(self, content,
                              fake_process: FakeProcess,
                              fs: FakeFilesystem) -> None:
        """
        Tests compile when prebuids are not present.
        """
        mp_common_args, flags, analysed_file = content

        fake_process.register(['sfc', '--version'], stdout='1.2.3')
        record = fake_process.register(['sfc', fake_process.any()])

        Path('/fab/proj/build_output/_prebuild').mkdir(parents=True)
        Path('/fab/proj/build_output/mod_def_1.mod').write_text("First module")
        Path('/fab/proj/build_output/mod_def_2.mod').write_text("Second module")

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(
            '/fab/proj/build_output/_prebuild/foofile.1ff6e93b2.o'
        )
        assert res == CompiledFile(input_fpath=analysed_file.fpath,
                                   output_fpath=expect_object_fpath)
        assert [call.args for call in record.calls] == [
            ['sfc', '-c', 'flag1', 'flag2', 'foofile',
             '-o', '/fab/proj/build_output/_prebuild/foofile.1ff6e93b2.o']
        ]

        # check the correct artefacts were generated.
        #
        # This is done before opening files in case hasehse have changed.
        #
        pb = mp_common_args.config.prebuild_folder
        assert artefacts is not None
        assert set(artefacts) == {
            pb / 'foofile.1ff6e93b2.o',
            pb / 'mod_def_2.188dd00a8.mod',
            pb / 'mod_def_1.188dd00a8.mod'
        }

        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_1.188dd00a8.mod'
        ).read_text() == "First module"
        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_2.188dd00a8.mod'
        ).read_text() == "Second module"

    def test_with_prebuild(self, content,
                           fs: FakeFilesystem,
                           fake_process: FakeProcess) -> None:
        """
        Tests compilation only if prebuidlds are not present.
        """
        mp_common_args, _, analysed_file = content

        fake_process.register(['sfc', '--version'], stdout='1.2.3')
        record = fake_process.register(['sfc', fake_process.any()])

        Path('/fab/proj/build_output/_prebuild').mkdir(parents=True)
        Path('/fab/proj/build_output/mod_def_1.mod').write_text("First module")
        Path('/fab/proj/build_output/mod_def_2.mod').write_text("Second module")
        Path(
            '/fab/proj/build_output/_prebuild/mod_def_1.188dd00a8.mod'
        ).write_text("First module")
        Path(
            '/fab/proj/build_output/_prebuild/mod_def_2.188dd00a8.mod'
        ).write_text("Second module")
        Path(
            '/fab/proj/build_output/_prebuild/foofile.1ff6e93b2.o'
        ).write_text("Object file")

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(
            '/fab/proj/build_output/_prebuild/foofile.1ff6e93b2.o'
        )

        # check the correct artefacts were generated.
        #
        # This is done before anything else in case hashes have changed.
        #
        pb = mp_common_args.config.prebuild_folder
        assert artefacts is not None
        assert set(artefacts) == {
            pb / 'foofile.1ff6e93b2.o',
            pb / 'mod_def_2.188dd00a8.mod',
            pb / 'mod_def_1.188dd00a8.mod'
        }

        assert [call.args for call in record.calls] == []
        assert res == CompiledFile(input_fpath=analysed_file.fpath,
                                   output_fpath=expect_object_fpath)

        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_1.188dd00a8.mod'
        ).read_text() == "First module"
        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_2.188dd00a8.mod'
        ).read_text() == "Second module"

    def test_file_hash(self, content, fs: FakeFilesystem, fake_process: FakeProcess) -> None:
        """
        Tests changing source hash leads to new module and object hashes.
        """
        mp_common_args, flags, analysed_file = content

        analysed_file._file_hash += 1

        fake_process.register(['sfc', '--version'], stdout='1.2.3')
        record = fake_process.register(['sfc', fake_process.any()])

        Path('/fab/proj/build_output/_prebuild').mkdir(parents=True)
        Path('/fab/proj/build_output/mod_def_1.mod').write_text("First module")
        Path('/fab/proj/build_output/mod_def_2.mod').write_text("Second module")
        Path(
            '/fab/proj/build_output/_prebuild/mod_def_1.188dd00a9.mod'
        ).write_text("First module")
        Path(
            '/fab/proj/build_output/_prebuild/mod_def_2.188dd00a9.mod'
        ).write_text("Second module")

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(
            '/fab/proj/build_output/_prebuild/foofile.1ff6e93b3.o'
        )
        assert res == CompiledFile(input_fpath=analysed_file.fpath,
                                   output_fpath=expect_object_fpath)
        assert [call.args for call in record.calls] == [
            ['sfc', '-c', 'flag1', 'flag2', 'foofile',
             '-o', '/fab/proj/build_output/_prebuild/foofile.1ff6e93b3.o']
        ]

        # check the correct artefacts were generated.
        #
        # This is done before opening the files incase hashes have changed.
        #
        pb = mp_common_args.config.prebuild_folder
        assert artefacts is not None
        assert set(artefacts) == {
            pb / 'foofile.1ff6e93b3.o',
            pb / 'mod_def_2.188dd00a9.mod',
            pb / 'mod_def_1.188dd00a9.mod'
        }

        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_1.188dd00a9.mod'
        ).read_text() == "First module"
        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_2.188dd00a9.mod'
        ).read_text() == "Second module"

    def test_flags_hash(self, content, fs: FakeFilesystem, fake_process: FakeProcess) -> None:
        """
        Tests changing compiler arguments changes generated object and
        module hashes. Not source modules.
        """
        mp_common_args, flags, analysed_file = content

        flags = ['flag1', 'flag3']
        mp_common_args.flags.flags_for_path.return_value = flags

        fake_process.register(['sfc', '--version'], stdout='1.2.3')
        record = fake_process.register(['sfc', fake_process.any()])

        Path('/fab/proj/build_output/_prebuild').mkdir(parents=True)
        Path('/fab/proj/build_output/mod_def_1.mod').write_text("First module")
        Path('/fab/proj/build_output/mod_def_2.mod').write_text("Second module")
        Path(
            '/fab/proj/build_output/_prebuild/mod_def_1.188dd00a8.mod'
        ).write_text("First module")
        Path(
            '/fab/proj/build_output/_prebuild/mod_def_2.188dd00a8.mod'
        ).write_text("Second module")

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(
            '/fab/proj/build_output/_prebuild/foofile.20030f987.o'
        )
        assert res == CompiledFile(input_fpath=analysed_file.fpath,
                                   output_fpath=expect_object_fpath)
        assert [call.args for call in record.calls] == [
            ['sfc', '-c', 'flag1', 'flag3', 'foofile',
             '-o', '/fab/proj/build_output/_prebuild/foofile.20030f987.o']
        ]

        # check the correct artefacts were generated.
        #
        # This is done before attempting to open files in case hashes have
        # changed.
        #
        pb = mp_common_args.config.prebuild_folder
        assert artefacts is not None
        assert set(artefacts) == {
            pb / 'foofile.20030f987.o',
            pb / 'mod_def_2.188dd00a8.mod',
            pb / 'mod_def_1.188dd00a8.mod'
        }

        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_1.188dd00a8.mod'
        ).read_text() == "First module"
        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_2.188dd00a8.mod'
        ).read_text() == "Second module"

    def test_deps_hash(self, content, fs: FakeFilesystem, fake_process: FakeProcess) -> None:
        """
        Tests changing a module dependency checksum causes a rebuild.
        The generated object hash should change but the generated module
        hashes should not.
        """
        mp_common_args, flags, analysed_file = content

        mp_common_args.mod_hashes['mod_dep_1'] += 1

        fake_process.register(['sfc', '--version'], stdout='1.2.3')
        record = fake_process.register(['sfc', fake_process.any()])

        Path('/fab/proj/build_output/_prebuild').mkdir(parents=True)
        Path('/fab/proj/build_output/mod_def_1.mod').write_text("First module")
        Path('/fab/proj/build_output/mod_def_2.mod').write_text("Second module")
        Path(
            '/fab/proj/build_output/_prebuild/mod_def_1.188dd00a8.mod'
        ).write_text("First module")
        Path(
            '/fab/proj/build_output/_prebuild/mod_def_2.188dd00a8.mod'
        ).write_text("Second module")

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(
            '/fab/proj/build_output/_prebuild/foofile.1ff6e93b3.o'
        )
        assert res == CompiledFile(input_fpath=analysed_file.fpath,
                                   output_fpath=expect_object_fpath)
        assert [call.args for call in record.calls] == [
            ['sfc', '-c', 'flag1', 'flag2', 'foofile',
             '-o', '/fab/proj/build_output/_prebuild/foofile.1ff6e93b3.o']
        ]

        # check the correct artefacts were created.
        #
        # This is done before attempting to open the files incase their
        # hashes have changed.
        #
        pb = mp_common_args.config.prebuild_folder
        assert artefacts is not None
        assert set(artefacts) == {
            pb / 'foofile.1ff6e93b3.o',
            pb / 'mod_def_2.188dd00a8.mod',
            pb / 'mod_def_1.188dd00a8.mod'
        }

        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_1.188dd00a8.mod'
        ).read_text() == "First module"
        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_2.188dd00a8.mod'
        ).read_text() == "Second module"

    def test_mod_missing(self, content, fs: FakeFilesystem, fake_process: FakeProcess) -> None:
        """
        Tests compilation on missing module.
        """
        mp_common_args, flags, analysed_file = content

        fake_process.register(['sfc', '--version'], stdout='1.2.3')
        record = fake_process.register(['sfc', fake_process.any()])

        Path('/fab/proj/build_output/_prebuild').mkdir(parents=True)
        Path('/fab/proj/build_output/mod_def_1.mod').write_text("First module")
        Path('/fab/proj/build_output/mod_def_2.mod').write_text("Second module")
        Path(
            '/fab/proj/build_output/_prebuild/mod_def_2.188dd00a8.mod'
        ).write_text("Second module")
        Path(
            '/fab/proj/build_output/_prebuild/foofile.1ff6e93b2.o'
        ).write_text("Object file")

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(
            '/fab/proj/build_output/_prebuild/foofile.1ff6e93b2.o'
        )
        assert res == CompiledFile(input_fpath=analysed_file.fpath,
                                   output_fpath=expect_object_fpath)
        assert [call.args for call in record.calls] == [
            ['sfc', '-c', 'flag1', 'flag2', 'foofile',
             '-o', '/fab/proj/build_output/_prebuild/foofile.1ff6e93b2.o']
        ]

        # check the correct artefacts were created.
        #
        # This is done before checking their contents to avoid problems
        # failing to poen the file if the checksum has changed.
        #
        pb = mp_common_args.config.prebuild_folder
        assert artefacts is not None
        assert set(artefacts) == {
            pb / 'foofile.1ff6e93b2.o',
            pb / 'mod_def_2.188dd00a8.mod',
            pb / 'mod_def_1.188dd00a8.mod'
        }

        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_1.188dd00a8.mod'
        ).read_text() == "First module"
        assert Path(
            '/fab/proj/build_output/_prebuild/mod_def_2.188dd00a8.mod'
        ).read_text() == "Second module"

    @mark.parametrize(['version', 'mod_hash', 'obj_hash'], [
        ('1.2.3', '188dd00a8', '1ff6e93b2'),
        ('9.8.7', '1b26306b2', '228f499bc')
    ])
    def test_obj_missing(self, content, version, mod_hash, obj_hash,
                         fs: FakeFilesystem, fake_process: FakeProcess) -> None:
        """
        Tests compilation of missing object. Also tests that different compiler
        version numbers lead to different hashes.
        """
        mp_common_args, flags, analysed_file = content

        fake_process.register(['sfc', '--version'], stdout=version)
        record = fake_process.register(['sfc', fake_process.any()])

        Path('/fab/proj/build_output/_prebuild').mkdir(parents=True)
        Path('/fab/proj/build_output/mod_def_1.mod').write_text("First module")
        Path('/fab/proj/build_output/mod_def_2.mod').write_text("Second module")
        Path(
            f'/fab/proj/build_output/_prebuild/mod_def_1.{mod_hash}.mod'
        ).write_text("First module")
        Path(
            f'/fab/proj/build_output/_prebuild/mod_def_2.{mod_hash}.mod'
        ).write_text("Second module")

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(
            f'/fab/proj/build_output/_prebuild/foofile.{obj_hash}.o'
        )
        assert res == CompiledFile(input_fpath=analysed_file.fpath,
                                   output_fpath=expect_object_fpath)
        assert [call.args for call in record.calls] == [
            ['sfc', '-c', 'flag1', 'flag2', 'foofile',
             '-o', f'/fab/proj/build_output/_prebuild/foofile.{obj_hash}.o']
        ]

        assert Path(
            f'/fab/proj/build_output/_prebuild/mod_def_1.{mod_hash}.mod'
        ).read_text() == "First module"
        assert Path(
            f'/fab/proj/build_output/_prebuild/mod_def_2.{mod_hash}.mod'
        ).read_text() == "Second module"

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert artefacts is not None
        assert set(artefacts) == {
            pb / f'foofile.{obj_hash}.o',
            pb / f'mod_def_2.{mod_hash}.mod',
            pb / f'mod_def_1.{mod_hash}.mod'
        }


class TestGetModHashes:
    """
    Tests of hashing functionality.
    """
    def test_vanilla(self, stub_tool_box, fs) -> None:
        """
        Tests hashing of every module in an analysed file.
        """
        Path('/fab_workspace/proj/build_output').mkdir(parents=True)
        Path('/fab_workspace/proj/build_output/foo.mod').write_text("Foo file.")
        Path('/fab_workspace/proj/build_output/bar.mod').write_text("Bar file.")
        Path('foo_mod.f90').touch()
        analysed_files = {
            AnalysedFortran('foo_mod.f90',
                            module_defs=['foo', 'bar'],
                            symbol_defs=['foo', 'bar'])
        }

        config = BuildConfig('proj', stub_tool_box,
                             fab_workspace=Path('/fab_workspace'))

        result = get_mod_hashes(analysed_files=analysed_files, config=config)

        assert result == {'foo': 3990191875, 'bar': 2746925363}
