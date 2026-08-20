from pathlib import Path
from stat import filemode
from time import localtime, strftime


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
