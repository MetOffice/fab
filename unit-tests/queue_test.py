##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from fab.queue import QueueManager


class TestQueueManager(object):
    def test_constructor(self):
        test_unit = QueueManager()
