from importlib import import_module

from pytest import fixture, mark


@fixture(scope="session")
def api_v3():
    return import_module("fab.api.v3")


exports = [
    "BuildScript",
    "FileTreeRepository",
    "GitRepository",
    "SVNRepository",
    "Project",
    "WriteOnceDict",
]


@mark.parametrize("name", ["__version__"] + exports)
def test_symbol(name, api_v3):
    assert hasattr(api_v3, name)


@mark.parametrize("name", exports)
def test_all(name, api_v3):
    assert name in api_v3.__all__
