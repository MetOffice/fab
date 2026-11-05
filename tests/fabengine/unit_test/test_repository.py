from pathlib import Path
from typing import ClassVar

from fabengine.repository import (
    FileTreeRepository,
    ReadDependencies,
    RepositoryException,
    default_source,
)
from pytest import fixture, mark, raises

IDENTITY = "test_repo"


@fixture(scope="session")
def source_dir(tmp_path_factory) -> Path:
    """
    Session-level fixture to set up a source tree.
    Runs whenever this test class is first initialised.
    """
    root = tmp_path_factory.mktemp(IDENTITY)
    return root


def default_func_success(dependencies_file) -> Path:
    return dependencies_file


def default_func_fail(dependencies_file) -> str:
    return ""


class TestDefaultSource:
    deps_with_source: ClassVar = {IDENTITY: {"source": source_dir, "ref": "deps_ref"}}
    deps_no_source: ClassVar = {IDENTITY: {"source": "", "ref": ""}}

    @mark.parametrize(
        "dependencies, source, ref, expected",
        [
            (deps_with_source, "source", "ref", ("source", "ref")),
            (deps_with_source, None, "ref", (source_dir, "ref")),
            (deps_with_source, None, None, (source_dir, "deps_ref")),
            (deps_no_source, None, None, (Path("dependencies.yaml"), "")),
        ],
    )
    def test_success(self, dependencies, source, ref, expected):
        data = ReadDependencies(None)
        data._dependencies_file = Path("dependencies.yaml")
        data._dependencies = dependencies
        assert (
            default_source(
                IDENTITY,
                data,
                source,
                ref,
                default_func_success,
            )
            == expected
        )

    def test_no_dependencies(self):
        with raises(RepositoryException, match=r"One of the source or dependencies.*"):
            default_source(
                IDENTITY, ReadDependencies(None), None, None, default_func_success
            )

    def test_missing_identity(self):
        data = ReadDependencies(None)
        data._dependencies_file = Path("dependencies.yaml")
        data._dependencies = {}
        with raises(
            RepositoryException,
            match=rf"Repo {IDENTITY} not found in provided dependencies file.",
        ):
            default_source(IDENTITY, data, None, None, default_func_success)

    def test_no_source(self):
        with raises(
            RepositoryException,
            match=rf"Unable to work out the correct source for {IDENTITY}",
        ):
            data = ReadDependencies(None)
            data._dependencies_file = Path("dependencies.yaml")
            data._dependencies = self.deps_no_source
            default_source(IDENTITY, data, None, None, default_func_fail)


class TestRepository:
    def test_source_is_local(self, source_dir):
        source = str(source_dir)
        assert FileTreeRepository(IDENTITY, source).source_is_local() is True
        assert (
            FileTreeRepository(IDENTITY, "ssh:git@github.com").source_is_local()
            is False
        )
