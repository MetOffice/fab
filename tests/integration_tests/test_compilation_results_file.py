from pathlib import Path

from fab.build_config import BuildConfig
from fab.steps.compile_fortran import CompileFortran
from fab.util import CompiledFile


def test_compilation_results(tmp_path):
    # write a few compilation results to file
    config = BuildConfig('foo')
    config.project_workspace = Path(tmp_path)

    compiled = {
        Path('main.f90'): CompiledFile(
            input_fpath=Path('main.f90'), output_fpath=Path('main.o'),
            source_hash=111, flags_hash=222, module_deps_hashes={'foo': 333, 'bar': 444}),
        Path('foo.f90'): CompiledFile(
            input_fpath=Path('foo.f90'), output_fpath=Path('foo.o'), source_hash=555, flags_hash=666),
        Path('bar.f90'): CompiledFile(
            input_fpath=Path('bar.f90'), output_fpath=Path('bar.o'), source_hash=777, flags_hash=888),
    }

    compiler = CompileFortran()
    compiler.write_compile_result(compiled=compiled, config=config)

    # read them back
    read_back = compiler.read_compile_result(config)

    assert read_back == compiled
