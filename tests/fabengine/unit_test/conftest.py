from multiprocessing import set_start_method
from pathlib import Path

from pytest import fixture


def pytest_configure(config):
    # Required to prevent multiprocessing failures >= 3.14.  This can
    # only be run once and must run before any other multiprocessing
    # actions
    try:
        set_start_method("fork")
    except RuntimeError:
        # Ignore errors caused by a second attempt to set the start
        # method
        pass


@fixture
def examples_directory() -> Path | None:
    """Top down search for an examples directory.

    Stopping points are either the root of the file system, the first
    directory on a different device, or the top directory of the
    repository.

    :return: full path to examples directory in the repository
    """

    path: Path = Path(__file__).resolve()
    root: Path = Path(path.root)
    dev: int = path.stat().st_dev

    while path != root and path.stat().st_dev == dev:
        target = path / "examples"
        if target.is_dir():
            return target
        if (path / ".git").is_dir():
            break
        path = path.parent

    return None


@fixture
def code_example(request, examples_directory: Path) -> Path:
    """Path to a source code example.

    :param request: a fixture request object to allow for indirect parametrisation.
    """
    return examples_directory / request.param
