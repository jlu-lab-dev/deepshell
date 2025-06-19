import sys
import pytest
from PyQt5 import QtCore, QtGui, QtTest, QtWidgets
from PyQt5.QtCore import QCoreApplication, QObject, Qt
from PyQt5.QtWidgets import *
from pytestqt.plugin import QtBot
from singleton_app import SingleApplication
# Import the main window module
from main_window import MainWin


@pytest.fixture(scope="module")
def qapp():
    """Create a QApplication instance for the test session."""
    app = SingleApplication.instance()
    if app is None:
        app = SingleApplication(sys.argv)
    yield app


@pytest.fixture(scope="module")
def qtbot_session(qapp, request):
    """Create a QtBot instance for the test session."""
    result = QtBot(qapp)
    yield result


@pytest.fixture(scope="module")
def main_window(qtbot_session):
    """Create a MainWin instance for testing."""
    available_geometry = QApplication.desktop().availableGeometry()
    width = 480
    height = available_geometry.height()
    window = MainWin(width, height - 48)   # minus title height
    window.show()
    QtTest.QTest.qWait(500)  # Wait for the window to be fully initialized
    yield window
    window.close()


def test_main_window_creation(main_window):
    """Test that the main window is created correctly."""
    assert main_window is not None
    assert isinstance(main_window, MainWin)
    assert main_window.isVisible()


def test_main_window_components(main_window):
    """Test that the main window has the expected components."""
    # Check for specific components in the main window
    # This will depend on the actual implementation of MainWin
    # For example:
    # assert main_window.findChild(QWidget, "chatWgt") is not None
    # assert main_window.findChild(QWidget, "input_field_widget") is not None
    pass


def test_main_window_interaction(main_window, qtbot_session):
    """Test interaction with the main window."""
    # Example of interacting with the main window
    # This will depend on the actual implementation of MainWin
    # For example:
    # button = main_window.findChild(QPushButton, "sendButton")
    # qtbot_session.mouseClick(button, Qt.LeftButton)
    # # QtTest.QTest.qWait(1000)  # Wait for the action to complete
    # pass 