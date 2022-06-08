"""
Test reading and writing analysis results.

"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from fab.dep_tree import AnalysedFile
from fab.steps.analyse import Analyse
from fab.util import HashedFile


def test_analysis_results():
    # using a physical analysis file, this tests:
    #   new source file
    #   changed source file
    #   previously analysed source file, unchanged
    #   source file no longer there

    # source folder before change
    previous_file_hashes = {
        Path('change.f90'): 111,
        Path('no_change.f90'): 222,
        Path('remove.f90'): 333,
    }

    # source folder after change
    latest_file_hashes = {
        Path('change.f90'): 123,
        Path('no_change.f90'): 222,
        Path('new.f90'): 444,
    }

    previous_results = {
        AnalysedFile(fpath=path, file_hash=file_hash) for path, file_hash in previous_file_hashes.items()}

    with TemporaryDirectory() as tmpdir:
        analyser = Analyse(root_symbol=None)

        # simulate the effect of calling run, in which the superclass sets up the _config attribute (is this too ugly?)
        analyser._config = mock.Mock(project_workspace=Path(tmpdir))

        # create the initial analysis file
        with analyser._new_analysis_file(unchanged=previous_results):
            pass

        # check it loads correctly with no changes detected
        loaded_results = analyser._load_analysis_results(previous_file_hashes)
        changed, unchanged = analyser._what_needs_reanalysing(
            prev_results=loaded_results, latest_file_hashes=previous_file_hashes)
        assert not changed
        assert unchanged == previous_results

        # check we correctly identify new, changed, unchanged and removed files
        loaded_results = analyser._load_analysis_results(latest_file_hashes)
        changed, unchanged = analyser._what_needs_reanalysing(
            prev_results=loaded_results, latest_file_hashes=latest_file_hashes)
        assert unchanged == {AnalysedFile(fpath=Path('no_change.f90'), file_hash=222)}
        assert changed == {
            HashedFile(fpath=Path('change.f90'), file_hash=123),
            HashedFile(fpath=Path('new.f90'), file_hash=444)
        }
