import os
from signal import SIGABRT, SIGINT, SIGTERM, getsignal

from fabengine.processes import SignalHandler


class TestSignalHandler:
    """Test signal handler class."""

    def test_core(self):
        """Check core features."""
        signaller = SignalHandler()

        assert signaller.stopping is False
        for sig in (SIGABRT, SIGINT, SIGTERM):
            assert getsignal(sig) == signaller._stop_process

    def test_handler(self):
        """Check signal sets _stopping to true."""
        signaller = SignalHandler()

        assert signaller.stopping is False
        os.kill(os.getpid(), SIGTERM)
        assert signaller.stopping is True

    def test_restore(self):
        """Check default signal handlers can be restored."""
        signaller = SignalHandler()
        signaller.restore_signals()

        for sig in (SIGABRT, SIGINT, SIGTERM):
            assert getsignal(sig) != signaller._stop_process
