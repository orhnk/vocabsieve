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
