from collections.abc import Callable
from multiprocessing import Process

try:
    from setproctitle import getproctitle, setproctitle  # type: ignore

    __set_titles = True
except ModuleNotFoundError:
    __set_titles = False

# todo: this shouldn't be hardwired
progname = "fabtoy"


def set_ps_name(func: Callable) -> Callable:
    """Set the process name to match the decorated function.

    If setproctitle support is available, change the name of the
    current process to match the name of the function or method
    currently being executed, allowing tasks to be easily identified
    in a ps listing.

    The previous function name is restored when the process returns or
    an exception occurs.
    """

    if not __set_titles:
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
