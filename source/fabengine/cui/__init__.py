from pathlib import Path
from stat import filemode
from time import localtime, strftime

from rich.console import Console  # type: ignore
from rich.tree import Tree  # type: ignore

from fabengine.actions import Action, WorkerException


def show_errors(console: Console, results: list[WorkerException]) -> None:
    if not results:
        return

    console.rule("[bold]Errors")

    for result in results:
        console.print(f"[red]{result.describe()}")


def show_stalled_actions(console: Console, remainder: list[Action]) -> None:
    """Display a tree summarising stalled actions."""

    if not remainder:
        return

    console.rule("[bold]Stalled Actions")

    tree = Tree("Actions")

    for action in remainder:
        branch = tree.add(f"{action}")
        satisfied = 0

        for prereq in action.prerequisites():
            if prereq.ready():
                satisfied += 1
                continue

            branch.add(f":cross_mark: [red]{prereq}")

        if satisfied > 0:
            deps = "dependency" if satisfied == 1 else "dependencies"
            branch.add(f"[green]{satisfied} {deps} satisified")

    console.print(tree)


def format_file_details(real: Path) -> str:
    """Information about a file in an ls-like format."""

    stat = real.stat()
    date = strftime("%F %H:%M:%S", localtime(stat.st_mtime))

    result = filemode(stat.st_mode)
    result += f" {stat.st_nlink:2d}"
    result += f" {stat.st_size:10d}"
    result += f" {date}"
    result += f" {real}"

    return result
