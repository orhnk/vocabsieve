import os
import sys

# Make the local checkout importable without requiring an editable install.
# This is especially useful in `nix develop` where we run tests against the
# working tree.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Ensure the application can initialize Qt during pytest collection in nix.
# (PYTEST_CURRENT_TEST is only set while tests are running, not during import.)
os.environ.setdefault("PYTEST_VERSION", "1")

import os

from PyQt5.QtWidgets import QApplication
import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():  # pragma: no cover
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
