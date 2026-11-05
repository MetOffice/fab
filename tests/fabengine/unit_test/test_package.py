##############################################################################
# (c) Crown copyright 2025 Met Office. All rights reserved.
# The file LICENCE, distributed with this code, contains details of the terms
# under which the code may be used.
##############################################################################
from pathlib import Path
from textwrap import dedent
from typing import Any

from fabengine.package import (
    IncludePath,
    LibraryName,
    LinkerPath,
    LinkType,
    Package,
    PackageException,
    VariableDefinition,
    partition_specification,
    pkg_config,
)
from pytest import FixtureRequest, MonkeyPatch, fixture, mark, raises


class TestPackage:
    def test_constructor(self):
        test_unit = Package(
            "my_lib-special4",
            (1, 2, 3, "rc", 4),
            (IncludePath(Path("/opt/my_stuff/include")),),
            (LinkerPath(Path("/opt/my_stuff/lib")), LibraryName("my_lib")),
        )
        assert test_unit.name == "my_lib-special4"
        assert test_unit.version == (1, 2, 3, "rc", 4)
        assert test_unit.compile_arguments == (
            IncludePath(Path("/opt/my_stuff/include")),
        )
        assert test_unit.link_arguments == (
            LinkerPath(Path("/opt/my_stuff/lib")),
            LibraryName("my_lib"),
        )


@fixture
def system_path(tmp_path: Path) -> Path:
    system_path = tmp_path / "usr" / "local"
    system_path.mkdir(parents=True)
    return system_path


@fixture
def system_pkg_path(system_path: Path, monkeypatch: MonkeyPatch) -> Path:
    pkg_path = system_path / "lib" / "pkg_config"
    pkg_path.mkdir(parents=True)
    monkeypatch.setenv("PKG_CONFIG_LIBDIR", str(pkg_path))
    return pkg_path


@fixture
def user_path(tmp_path: Path) -> Path:
    user_path = tmp_path / "opt" / "special"
    user_path.mkdir(parents=True)
    return user_path


@fixture
def user_pkg_path(user_path: Path, monkeypatch: MonkeyPatch) -> Path:
    pkg_path = user_path / "lib" / "pkg_config"
    pkg_path.mkdir(parents=True)
    monkeypatch.setenv("PKG_CONFIG_PATH", str(pkg_path))
    return pkg_path


class TestPartitionSpecification:
    @mark.parametrize(
        "specification, name, operator, value",
        [
            ("bare_test", "bare_test", "", ""),
            ("less_than < 1.2.3", "less_than", "<", "1.2.3"),
            ("less_than_or_equal <= 2.3.4", "less_than_or_equal", "<=", "2.3.4"),
            ("equal == 3.4.5", "equal", "==", "3.4.5"),
            ("greater_than > 4.5.6", "greater_than", ">", "4.5.6"),
            ("greater_than_or_equal >= 5.6.7", "greater_than_or_equal", ">=", "5.6.7"),
            ("no_spaces==6.7.8", "no_spaces", "==", "6.7.8"),
        ],
    )
    def test_operation(self, specification: str, name: str, operator: str, value: str):
        assert partition_specification(specification) == (name, operator, value)


class TestPkgConfig:
    @mark.parametrize("pkg_path_fixture", ("system_pkg_path", "user_pkg_path"))
    @mark.parametrize("package_name", ("single", "pot_hole", "CamelCase"))
    def test_name(
        self, pkg_path_fixture: str, package_name: str, request: FixtureRequest
    ):
        """
        Checks some likely library names.

        Libraries on both system and user paths.
        """
        pkg_path: Path = request.getfixturevalue(pkg_path_fixture)
        package_file = pkg_path / f"{package_name}.pc"
        lib_path = pkg_path.parent
        inc_path = lib_path.parent / "include"
        package_file.write_text(
            dedent(
                f"""
                Name: {package_name}
                Version: 1.0.1
                Description: Test package.
                URL: http://example.com/{package_name}
                Cflags: -I{inc_path}/{package_name}
                Cflags.private: -I{inc_path}/{package_name}/static
                Libs: -L{lib_path}/simple -lsimple
                Libs.private: -L {lib_path}/static -l static
                """
            )
        )
        result = pkg_config(package_name)
        assert result.name == package_name
        assert result.version == (1, 0, 1)
        assert result.compile_arguments == (IncludePath(inc_path / package_name),)
        assert result.link_arguments == (
            LinkerPath(lib_path / "simple"),
            LibraryName("simple"),
        )

    @mark.parametrize(
        "version, expected",
        [
            ("", {"version": ()}),
            ("1", {"version": (1,)}),
            ("1.2", {"version": (1, 2)}),
            ("1.2.3", {"version": (1, 2, 3)}),
            ("1.2.dev1", {"version": (1, 2, "dev1")}),
            ("2.3.dev.2", {"version": (2, 3, "dev", 2)}),
        ],
    )
    def test_version(
        self,
        version: str,
        expected: dict[str, Any],
        user_path: Path,
        user_pkg_path: Path,
        tmp_path: Path,
    ):
        """
        Checks various version number formats.

        Libraries on user paths.
        """
        (user_pkg_path / "test.pc").write_text(
            dedent(
                f"""
                Name: test
                Version: {version}
                Description: Many versions.
                URL: http://example.com/version
                Cflags: -I/{user_path.relative_to(tmp_path)}/include
                Cflags.private: -I/{user_path.relative_to(tmp_path)}/include
                Libs: -L/{user_path.relative_to(tmp_path)}/lib -lversion
                Libs.private: -L/{user_path.relative_to(tmp_path)}/lib -l static
                """
            )
        )

        result = pkg_config("test")
        assert result.name == "test"
        assert result.version == expected["version"]
        assert result.compile_arguments == (IncludePath(Path("/opt/special/include")),)
        assert result.link_arguments == (
            LinkerPath(Path("/opt/special/lib")),
            LibraryName("version"),
        )

    @mark.parametrize(
        "arg_str, expected",
        [
            ("", ()),
            (
                "-I/usr/local/lib/special",
                (IncludePath(Path("/usr/local/lib/special")),),
            ),
            (
                "-I/usr/local/lib/special -I/usr/local/lib/other",
                (
                    IncludePath(Path("/usr/local/lib/special")),
                    IncludePath(Path("/usr/local/lib/other")),
                ),
            ),
            ("-I /usr/local/special", (IncludePath(Path("/usr/local/special")),)),
        ],
    )
    def test_compile_arguments(
        self,
        arg_str: str,
        expected: tuple[str],
        user_path: Path,
        user_pkg_path: Path,
        tmp_path: Path,
    ):
        """
        Checks compiler path arguments are compressed.

        Libraries on user paths.
        """
        (user_pkg_path / "test.pc").write_text(
            dedent(
                f"""
                Name: test
                Version: 1.0.0
                Description: Many versions.
                URL: http://example.com/version
                Cflags: {arg_str}
                Cflags.private:
                Libs: -L/{user_path.relative_to(tmp_path)}/lib -lversion
                Libs.private: -L/{user_path.relative_to(tmp_path)}/lib -l static
                """
            )
        )

        result = pkg_config("test")
        assert result.name == "test"
        assert result.version == (1, 0, 0)
        assert result.compile_arguments == expected
        assert result.link_arguments == (
            LinkerPath(Path("/opt/special/lib")),
            LibraryName("version"),
        )

    @mark.parametrize(
        "arg_str, expected",
        [
            ("", ()),
            (
                "-L/usr/local/lib/special -lspecial",
                (LinkerPath(Path("/usr/local/lib/special")), LibraryName("special")),
            ),
            (
                "-L/usr/local/lib/special -lspecial -L/usr/local/lib/other -lother",
                (
                    LinkerPath(Path("/usr/local/lib/special")),
                    LibraryName("special"),
                    LinkerPath(Path("/usr/local/lib/other")),
                    LibraryName("other"),
                ),
            ),
            (
                "-L /usr/local/special -l special",
                (LinkerPath(Path("/usr/local/special")), LibraryName("special")),
            ),
        ],
    )
    def test_link_arguments(
        self,
        arg_str: str,
        expected: tuple[str],
        user_path: Path,
        user_pkg_path: Path,
        tmp_path: Path,
    ):
        """
        Checks linker path arguments are compressed.

        Libraries on user paths.
        """
        (user_pkg_path / "test.pc").write_text(
            dedent(
                f"""
                Name: test
                Version: 1.0.0
                Description: Many versions.
                URL: http://example.com/version
                Cflags: -I/opt/special/include
                Cflags.private: -I/opt/special/include
                Libs: {arg_str}
                Libs.private:
                """
            )
        )

        result = pkg_config("test")
        assert result.name == "test"
        assert result.version == (1, 0, 0)
        assert result.compile_arguments == (IncludePath(Path("/opt/special/include")),)
        assert result.link_arguments == expected

    @mark.parametrize(
        "link_type, expected",
        [(LinkType.SHARED, "--shared"), (LinkType.STATIC, "--static")],
    )
    def test_link_type(
        self,
        link_type: LinkType,
        expected: str,
        user_path: Path,
        user_pkg_path: Path,
        tmp_path: Path,
    ):
        """
        Checks shared and static linking.

        Mock pkg_config acts as though library is on system path.
        """
        (user_pkg_path / "test.pc").write_text(
            dedent(
                """
                Name: test
                Version: 1.0.0
                Description: Many versions.
                URL: http://example.com/version
                Cflags: -I/opt/special/include
                Cflags.private: -I/opt/special/include/private
                Libs: -L/opt/special/lib -l test
                Libs.private: -L /opt/special/lib/private -ltest-private
                """
            )
        )

        result = pkg_config("test", link_type=link_type)
        assert result.name == "test"
        assert result.version == (1, 0, 0)
        if link_type == LinkType.SHARED:
            assert result.compile_arguments == (
                IncludePath(Path("/opt/special/include")),
            )
            assert result.link_arguments == (
                LinkerPath(Path("/opt/special/lib")),
                LibraryName("test"),
            )
        elif link_type == LinkType.STATIC:
            assert result.compile_arguments == (
                IncludePath(Path("/opt/special/include")),
                IncludePath(Path("/opt/special/include/private")),
            )
            assert result.link_arguments == (
                LinkerPath(Path("/opt/special/lib")),
                LibraryName("test"),
                LinkerPath(Path("/opt/special/lib/private")),
                LibraryName("test-private"),
            )
        else:
            assert False

    def test_pcfiledir(self, user_pkg_path: Path):
        pc_file = user_pkg_path / "relative.pc"
        pc_file.write_text(
            dedent(
                """
                Name: relative
                Version: 1.2.3
                Description: Uses paths relative to this file.
                URL: http://example.com/relative
                Cflags: -I${pcfiledir}/../../include
                Cflags.private: -I${pcfiledir}/../../include/private
                Libs: -L${pcfiledir}/.. -l relative
                Libs.private: -L ${pcfiledir}/../private -lrelative-private
                """
            )
        )
        result = pkg_config("relative")
        assert result.name == "relative"
        assert result.version == (1, 2, 3)
        assert result.compile_arguments == (
            IncludePath(user_pkg_path / "../../include"),
        )
        assert result.link_arguments == (
            LinkerPath(user_pkg_path / ".."),
            LibraryName("relative"),
        )

    def test_tree(
        self,
        user_path: Path,
        user_pkg_path: Path,
        system_path: Path,
        system_pkg_path: Path,
        tmp_path: Path,
    ):
        """
        Checks recursive dependencies.
        """
        (system_pkg_path / "parent.pc").write_text(
            dedent(
                """
                Name: parent
                Version: 1.0.0
                Description: Is a parent thing.
                URL: http://example.com/parent
                Cflags: -I/opt/parent/include
                Libs: -L/opt/parent/lib -lparent
                """
            )
        )

        (user_pkg_path / "child.pc").write_text(
            dedent(
                """
                Name: child
                Version: 1.0.0
                Description: Depends on parent thing.
                URL: http://example.com/child
                Requires: parent
                Cflags: -I/opt/child/include
                Libs: -L/opt/child/lib -lchild
                """
            )
        )

        result = pkg_config("child")
        assert result.name == "child"
        assert result.version == (1, 0, 0)
        assert result.compile_arguments == (
            IncludePath(Path("/opt/child/include")),
            IncludePath(Path("/opt/parent/include")),
        )
        assert result.link_arguments == (
            LinkerPath(Path("/opt/child/lib")),
            LibraryName("child"),
            LinkerPath(Path("/opt/parent/lib")),
            LibraryName("parent"),
        )

    @mark.parametrize(
        "version, expected",
        [("0.1.0", None), ("1.2.2", None), ("1.2.3", (1, 2, 3)), ("1.2.4", (1, 2, 4))],
    )
    def test_specification(
        self, version: str, expected: tuple[int] | None, user_pkg_path: Path
    ):
        (user_pkg_path / "test.pc").write_text(
            dedent(
                f"""
                Name: test
                Version: {version}
                Description: Many versions.
                URL: http://example.com/test
                Cflags: -I/opt/test/include
                Libs: -Lopt/test/lib -ltest
                """
            )
        )
        if expected is None:
            with raises(PackageException):
                _ = pkg_config("test >= 1.2.3")
        else:  # Package should fulfil specification
            result = pkg_config("test >= 1.2.3")
            assert result.name == "test"
            assert result.version == expected

    def test_variable_definitions(self, user_pkg_path: Path):
        (user_pkg_path / "defining.pc").write_text(
            dedent(
                """
                Name: defining
                Version: 0.0.0
                Description: Inclusion and definition.
                URL: http://example.com/defining
                Cflags: -I/opt/defining/include -DSPECIAL=EXTRA -D PRESENT
                Libs: -L/opt/defining/lib -l defining
                """
            )
        )
        result = pkg_config("defining")
        assert result.name == "defining"
        assert result.version == (0, 0, 0)
        assert result.compile_arguments == (
            IncludePath(Path("/opt/defining/include")),
            VariableDefinition("SPECIAL", "EXTRA"),
            VariableDefinition("PRESENT"),
        )
        assert result.link_arguments == (
            LinkerPath(Path("/opt/defining/lib")),
            LibraryName("defining"),
        )
