"""Shared, isolated test configuration for BMTB."""
import os
import tempfile

# constants.py reads APPDATA at import time, so isolate it before test modules
# import any application modules.
_TEST_APPDATA = tempfile.mkdtemp(prefix="bmtb-tests-")
os.environ["APPDATA"] = _TEST_APPDATA
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Create one offscreen Qt application for widget/settings tests."""
    pytest.importorskip("PyQt5")
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
