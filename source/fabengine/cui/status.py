import atexit
import os
import sys
from collections.abc import Callable
from multiprocessing import Process

try:
    from setproctitle import getproctitle, setproctitle  # type: ignore

    __set_process_titles = True
except ModuleNotFoundError:
    __set_process_titles = False

# todo: this shouldn't be hardwired
progname = "fabtoy"


def set_terminal_title(build_name: str | None = None) -> None:
    """Set the terminal title for the duration of the application.

    If the current terminal is interactive and is not of a type with
    limited functionality, use xterm control sequences to push the
    current title onto the stack and set a new one.  Also register a
    function to restore the previous title when the application exits.
    """

    if not os.isatty(sys.stdout.fileno()):
        # Do nothing if output is not a terminal
        return

    title = progname
    if build_name is not None:
        title += f": {build_name}"

    if os.getenv("TERM", "dumb") not in ("ansi", "dumb", "vt100"):
        # If terminal is not a small subset of limited terminals
        sys.stdout.write("\033[22;0t")
        sys.stdout.write(f"\033]2;{title}\007")
        sys.stdout.flush()

        atexit.register(_restore_terminal_title)


def _restore_terminal_title() -> None:
    """Restore the previous terminal title.

    Pop the previous terminal title off the stack and use it.  This
    function should only be called from atexit.register, and only if
    the application has already pushed a title onto the stack.
    """

    sys.stdout.write("\033[23;0t")
    sys.stdout.flush()


def set_ps_name(func: Callable) -> Callable:
    """Set the process name to match the decorated function.

    If setproctitle support is available, change the name of the
    current process to match the name of the function or method
    currently being executed, allowing tasks to be easily identified
    in a ps listing.

    The previous function name is restored when the process returns or
    an exception occurs.
    """

    if not __set_process_titles:
        # Return the function if titles are not available
        return func

    def wrapper(*args, **kwargs):
        """Closure which sets the process name field."""

        before = getproctitle()

        title = f"{progname}: "
        if args and isinstance(args[0], Process):
            # Use the Process name attribute
            title += f"{args[0].name}"
        else:
            # Use the method or function name
            title += f"{func.__qualname__}"

        setproctitle(title)
        try:
            result = func(*args, **kwargs)
        finally:
            setproctitle(before)

        return result

    return wrapper
