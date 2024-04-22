# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''This file is read by pytest and provides common fixtures.
'''

from unittest import mock

import pytest

from fab.newtools import Categories, Compiler


@pytest.fixture
def mock_c_compiler():
    '''Provides a mock C-compiler.'''
    mock_compiler = Compiler("mock_compiler", "mock_exec",
                             Categories.C_COMPILER)
    mock_compiler.run = mock.Mock()
    mock_compiler._version = "1.2.3"
    return mock_compiler
