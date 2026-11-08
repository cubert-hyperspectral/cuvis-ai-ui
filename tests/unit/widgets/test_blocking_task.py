"""Tests for the runner that keeps blocking calls off the UI thread."""

import threading
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QProgressDialog, QPushButton

from cuvis_ai_ui.grpc.client import OperationCancelled
from cuvis_ai_ui.server import SERVER_READY_TIMEOUT
from cuvis_ai_ui.widgets.blocking_task import (
    TaskStatus,
    run_blocking,
    wait_for_server,
)


def _dialog() -> QProgressDialog | None:
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QProgressDialog) and widget.isVisible():
            return widget
    return None


def _later(ms, action):
    QTimer.singleShot(ms, action)


def _click_cancel():
    dialog = _dialog()
    assert dialog is not None
    dialog.findChild(QPushButton).click()


def _wait_for_cancel(stop: threading.Event):
    while not stop.wait(0.01):
        pass
    raise OperationCancelled


def test_a_returned_value_is_done(qapp):
    result = run_blocking(None, "Title", "Working...", lambda stop: 42)
    assert result.status is TaskStatus.DONE
    assert result.value == 42
    assert result.error == ""


def test_an_exception_is_failed_with_its_message(qapp):
    def broken(stop):
        raise RuntimeError("server went away")

    result = run_blocking(None, "Title", "Working...", broken)
    assert result.status is TaskStatus.FAILED
    assert result.error == "server went away"
    assert result.value is None


def test_an_exception_without_a_message_names_its_type(qapp):
    def broken(stop):
        raise KeyError

    assert run_blocking(None, "Title", "Working...", broken).error == "KeyError"


def test_the_dialog_shows_and_the_event_loop_runs_during_the_work(qapp):
    """The dialog is up at once and Qt keeps processing events, so windows
    repaint while the worker blocks."""
    seen = {}
    release = threading.Event()

    def look():
        dialog = _dialog()
        seen["visible"] = dialog is not None
        seen["text"] = dialog.labelText() if dialog else None
        seen["title"] = dialog.windowTitle() if dialog else None
        seen["modality"] = dialog.windowModality() if dialog else None
        release.set()

    _later(30, look)
    result = run_blocking(
        None, "Connecting", "Connecting to localhost:50200...", lambda s: release.wait(5)
    )

    assert result.status is TaskStatus.DONE
    assert seen == {
        "visible": True,
        "text": "Connecting to localhost:50200...",
        "title": "Connecting",
        "modality": Qt.WindowModality.ApplicationModal,
    }
    assert _dialog() is None


def test_cancel_sets_the_event_and_reports_cancelled(qapp):
    _later(30, _click_cancel)
    result = run_blocking(None, "Title", "Working...", _wait_for_cancel)
    assert result.status is TaskStatus.CANCELLED
    assert _dialog() is None


def test_cancel_waits_for_the_worker_and_says_so(qapp):
    """After Cancel the runner keeps a modal 'Cancelling...' dialog up until the
    worker returns, so nothing else can touch the client meanwhile."""
    release = threading.Event()
    seen = {}

    def slow_to_stop(stop):
        stop.wait(5)
        release.wait(5)
        raise OperationCancelled

    def look_then_release():
        dialog = _dialog()
        seen["text"] = dialog.labelText() if dialog else None
        seen["buttons"] = len(dialog.findChildren(QPushButton)) if dialog else None
        release.set()

    _later(30, _click_cancel)
    _later(150, look_then_release)
    result = run_blocking(None, "Title", "Working...", slow_to_stop)

    assert result.status is TaskStatus.CANCELLED
    assert release.is_set()
    assert seen["text"] == "Cancelling..."
    assert seen["buttons"] == 0


@pytest.mark.parametrize("how", ["escape", "close"])
def test_escape_and_closing_the_dialog_cancel_too(qapp, how):
    def dismiss():
        dialog = _dialog()
        assert dialog is not None
        if how == "escape":
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        else:
            dialog.close()

    _later(30, dismiss)
    assert (
        run_blocking(None, "Title", "Working...", _wait_for_cancel).status is TaskStatus.CANCELLED
    )


@pytest.mark.parametrize(
    "gestures",
    [("close",), ("cancel", "escape"), ("cancel", "close"), ("escape", "close")],
)
def test_no_dismissal_takes_the_dialog_down_before_the_worker_returns(qapp, gestures):
    """Esc or the close button after a Cancel, or closing the window outright,
    must not leave the windows unblocked while the worker still runs."""
    release = threading.Event()
    held = {}
    seen = {}

    def slow_to_stop(stop):
        stop.wait(5)
        release.wait(5)
        raise OperationCancelled

    def dismiss(gesture):
        dialog = held.setdefault("dialog", _dialog())
        assert dialog is not None
        if gesture == "cancel":
            dialog.findChild(QPushButton).click()
        elif gesture == "escape":
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        else:
            dialog.close()

    def look_then_release():
        dialog = held["dialog"]
        seen["visible"] = dialog.isVisible()
        seen["text"] = dialog.labelText()
        release.set()

    for i, gesture in enumerate(gestures):
        _later(30 + 60 * i, lambda g=gesture: dismiss(g))
    _later(300, look_then_release)
    result = run_blocking(None, "Title", "Working...", slow_to_stop)

    assert result.status is TaskStatus.CANCELLED
    assert seen == {"visible": True, "text": "Cancelling..."}
    assert _dialog() is None


def test_a_value_returned_after_cancel_is_still_done(qapp):
    """Work that finished anyway is used: discarding a connect that went through
    would leave its server session open."""

    def finishes_anyway(stop):
        stop.wait(5)
        return "connected"

    _later(30, _click_cancel)
    result = run_blocking(None, "Title", "Working...", finishes_anyway)
    assert result.status is TaskStatus.DONE
    assert result.value == "connected"


def test_wait_for_server_waits_on_the_manager_with_the_stop_event(qapp, tmp_path):
    manager = Mock()
    manager.port = 50200
    manager.log_path = tmp_path / "server.log"
    manager.wait_ready.return_value = True

    result = wait_for_server(manager, None)

    assert result.status is TaskStatus.DONE and result.value is True
    kwargs = manager.wait_ready.call_args.kwargs
    assert kwargs["timeout"] == SERVER_READY_TIMEOUT
    assert isinstance(kwargs["stop"], threading.Event)


def test_wait_for_server_names_the_port_and_the_log(qapp, tmp_path):
    manager = Mock()
    manager.port = 50200
    manager.log_path = tmp_path / "server.log"
    seen = {}
    release = threading.Event()

    def look():
        seen["text"] = _dialog().labelText()
        release.set()

    manager.wait_ready.side_effect = lambda timeout, stop: release.wait(5)
    _later(30, look)
    wait_for_server(manager, None)

    assert "50200" in seen["text"]
    assert str(tmp_path / "server.log") in seen["text"]
