from logging import DEBUG, INFO, WARNING
from pathlib import Path
from textwrap import dedent

from fabengine.entry import (
    command_line,
    instantiate_build_script,
    parse_libmap,
)
from fabengine.package import (
    IncludePath,
    LibraryName,
    LinkerPath,
    VariableDefinition,
)
from fabengine.work_queue import QueueStrategy
from pytest import mark, raises


class TestParseLibMap:
    @mark.parametrize(
        "variant, name", (("bare", "bare"), ("some:", "some"), ("other::", "other"))
    )
    def test_basic(self, variant: str, name: str):
        package = parse_libmap(variant)
        assert package.name == name
        assert package.version == ()
        assert package.compile_arguments == ()
        assert package.link_arguments == (LibraryName(name),)

    @mark.parametrize(
        "first_carg, first_carg_list",
        (("/usr/include", [IncludePath(Path("/usr/include"))]), ("", [])),
    )
    @mark.parametrize(
        "second_carg, second_carg_list",
        (
            ("/usr/local/include", [IncludePath(Path("/usr/local/include"))]),
            ("", []),
        ),
    )
    def test_compiler_include_arguments(
        self,
        first_carg: str,
        first_carg_list: list[IncludePath],
        second_carg: str,
        second_carg_list: list[IncludePath],
    ):
        carg_strs: list[str] = []
        cargs_list: list[IncludePath] = []
        if first_carg:
            carg_strs.append(first_carg)
            cargs_list.extend(first_carg_list)
        if second_carg:
            carg_strs.append(second_carg)
            cargs_list.extend(second_carg_list)
        specification = "test:" + ",".join(carg_strs)
        package = parse_libmap(specification)
        assert package.name == "test"
        assert package.version == ()
        assert package.compile_arguments == tuple(cargs_list)
        assert package.link_arguments == (LibraryName("test"),)

    @mark.parametrize(
        "first_carg, first_carg_list",
        (
            ("special=1", [VariableDefinition("special", "1")]),
            ("bare", [VariableDefinition("bare")]),
            ("", []),
        ),
    )
    @mark.parametrize(
        "second_carg, second_carg_list",
        (
            ("special=yes", [VariableDefinition("special", "yes")]),
            ("lonely", [VariableDefinition("lonely")]),
            ("", []),
        ),
    )
    def test_compiler_variable_arguments(
        self,
        first_carg: str,
        first_carg_list: list[VariableDefinition],
        second_carg: str,
        second_carg_list: list[VariableDefinition],
    ):
        carg_strs: list[str] = []
        cargs_list: list[VariableDefinition] = []
        if first_carg:
            carg_strs.append(first_carg)
            cargs_list.extend(first_carg_list)
        if second_carg:
            carg_strs.append(second_carg)
            cargs_list.extend(second_carg_list)
        specification = "test::" + ",".join(carg_strs)
        package = parse_libmap(specification)
        assert package.name == "test"
        assert package.version == ()
        assert package.compile_arguments == tuple(cargs_list)
        assert package.link_arguments == (LibraryName("test"),)

    @mark.parametrize(
        "first_larg, first_larg_list",
        (("/usr/lib", [LinkerPath(Path("/usr/lib"))]), ("", [])),
    )
    @mark.parametrize(
        "second_larg, second_larg_list",
        (("/usr/local/lib", [LinkerPath(Path("/usr/local/lib"))]), ("", [])),
    )
    def test_linker_path_arguments(
        self,
        first_larg: str,
        first_larg_list: list[LinkerPath],
        second_larg: str,
        second_larg_list: list[LinkerPath],
    ):
        larg_strs: list[str] = []
        largs_list: list[LinkerPath] = []
        if first_larg:
            larg_strs.append(first_larg)
            largs_list.extend(first_larg_list)
        if second_larg:
            larg_strs.append(second_larg)
            largs_list.extend(second_larg_list)
        specification = "test:::" + ",".join(larg_strs)
        package = parse_libmap(specification)
        assert package.name == "test"
        assert package.version == ()
        assert package.compile_arguments == ()
        assert package.link_arguments == tuple(largs_list) + (LibraryName("test"),)

    @mark.parametrize(
        "first_larg, first_larg_list",
        (("libspesh", [LibraryName("libspesh")]), ("", [])),
    )
    @mark.parametrize(
        "second_larg, second_larg_list",
        (("extraspesh", [LibraryName("extraspesh")]), ("", [])),
    )
    def test_linker_library_arguments(
        self,
        first_larg: str,
        first_larg_list: list[LibraryName],
        second_larg: str,
        second_larg_list: list[LibraryName],
    ):
        larg_strs: list[str] = []
        largs_list: list[LibraryName] = []
        if first_larg:
            larg_strs.append(first_larg)
            largs_list.extend(first_larg_list)
        if second_larg:
            larg_strs.append(second_larg)
            largs_list.extend(second_larg_list)
        specification = "test::::" + ",".join(larg_strs)
        package = parse_libmap(specification)
        assert package.name == "test"
        assert package.version == ()
        assert package.compile_arguments == ()
        assert package.link_arguments == tuple(largs_list) + (LibraryName("test"),)


class TestCommandline:
    def test_default(self):
        options = command_line([])
        assert options.fabfile == Path("Fabfile")
        assert options.jobs == 1
        assert options.work_dir == Path("work")
        assert options.verbose is None
        assert options.debug is None
        assert options.user_level == WARNING
        assert options.system_level == WARNING
        assert options.monitor is True
        assert options.queue_strategy == QueueStrategy.ALWAYS_TO_BACK
        assert options.timing_file is None
        assert options.logfile is None
        assert options.save_archive is None
        assert options.extract_archive is None

    @mark.parametrize("argument", ("--fabfile", "-f"))
    def test_fabfile(self, argument: str):
        options = command_line([argument, "cheesy/beef.script"])
        assert options.fabfile == Path("cheesy/beef.script")

    @mark.parametrize("argument", ("--jobs", "-j"))
    def test_jobs(self, argument: str):
        options = command_line([argument, "3"])
        assert options.jobs == 3

    @mark.parametrize("argument", ("--work-dir", "-w"))
    def test_work_dir(self, argument: str):
        options = command_line([argument, "scritchy/scratchy"])
        assert options.work_dir == Path("scritchy/scratchy")

    @mark.parametrize(
        "args, path",
        [
            (["-b", "blue"], "work/blue"),
            (["-w", "danish", "-b", "blue"], "danish/blue"),
            (["-b", "/brie"], "/brie"),
            (["-b", "/brie", "-w", "danish"], "/brie"),
        ],
        ids=["build", "work and build", "absolute build", "absolute build and work"],
    )
    def test_bin_dir(self, args: list[str], path: str):
        options = command_line(args)
        assert options.bin_dir == Path(path)

    @mark.parametrize(
        "argument, count, level",
        [
            ("--verbose", 1, INFO),
            ("-v", 1, INFO),
            ("-vv", 2, DEBUG),
            ("-vvv", 3, DEBUG),
        ],
    )
    def test_verbose(self, argument: str, count: int, level: int):
        options = command_line([argument])
        assert options.verbose == count
        assert options.user_level == level
        assert options.system_level == WARNING

    @mark.parametrize(
        "argument, count, level",
        [("--debug", 1, INFO), ("-d", 1, INFO), ("-dd", 2, DEBUG), ("-ddd", 3, DEBUG)],
    )
    def test_debug(self, argument: str, count: int, level: int):
        options = command_line([argument])
        assert options.debug == count
        assert options.system_level == level
        assert options.user_level == WARNING

    def test_no_monitor(self):
        options = command_line(["--no-monitor"])
        assert options.monitor is False

    @mark.parametrize(
        "strategy",
        ("always_to_back", "new_to_front", "sentinel_magic", "sentinel_extra_magic"),
    )
    def test_queue_strategy(self, strategy: str):
        options = command_line(["--queue-strategy", strategy])
        assert options.queue_strategy == QueueStrategy[strategy.upper()]

    def test_timing_file(self):
        options = command_line(["--timing-file", "wibble.txt"])
        assert options.timing_file == Path("wibble.txt")

    @mark.parametrize("argument", ("--logfile", "-l"))
    def test_logfile(self, argument: str):
        options = command_line([argument, "lymeswold.log"])
        assert options.logfile == Path("lymeswold.log")

    def test_save_archive(self):
        options = command_line(["--save-archive", "appenzeller.tar.gz"])
        assert options.save_archive == Path("appenzeller.tar.gz")

    def test_extract_archive(self):
        options = command_line(["--extract-archive", "gruyere.tar.gz"])
        assert options.extract_archive == Path("gruyere.tar.gz")


class TestInstantiateBuildScript:
    @mark.parametrize("name", ("Fabfile", "something.fabfile"))
    def test_success(self, name: str, tmp_path: Path):
        test_file = tmp_path / name
        test_file.write_text(
            dedent(
                """
                from fabengine.build_script import BuildScript

                class Something(BuildScript):
                    pass
                """
            )
        )
        instantiate_build_script(test_file)

    def test_missing_file(self, tmp_path: Path):
        with raises(FileNotFoundError):
            instantiate_build_script(tmp_path / "Fabfile")

    def test_confusing_file(self, tmp_path: Path):
        with raises(RuntimeError):
            instantiate_build_script(tmp_path / "some.other")

    def test_empty_file(self, tmp_path: Path):
        """
        Tests source file empty of a build script class.
        """
        test_file = tmp_path / "Fabfile"
        test_file.write_text(
            dedent(
                """
                from sys import exit

                if __name__ == '__main__':
                    exit(2)
                """
            )
        )
        with raises(RuntimeError):
            instantiate_build_script(test_file)
