from pathlib import Path
from re import match

from fabengine.cui import format_file_details


def test_format_file_details(tmp_path: Path):

    filename = tmp_path / "sample.txt"
    filename.write_text("hello!")

    result = format_file_details(filename)

    assert match(
        r"-rw-r--r--\s+1\s+6\s+\d+-\d+-\d+\s+\d+:\d+:\d+\s+.*?sample.txt$",
        result,
    )
