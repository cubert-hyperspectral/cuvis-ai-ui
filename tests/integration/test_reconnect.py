"""Reconnecting through Tools > Connect to Server in local mode."""

import threading
from unittest.mock import MagicMock, patch

import pytest

from cuvis_ai_ui.grpc.client import CuvisAIClient, OperationCancelled
from cuvis_ai_ui.main_window import MainWindow
from cuvis_ai_ui.widgets.blocking_task import SERVER_WAIT_CANCELLED


def _local_settings(port=50051):
    return {"mode": "local", "host": "localhost", "port": port, "auto_start": True}


def _connected_client(host="localhost", port=50051):
    """A real client holding session s1 on a mocked channel and stub."""
    client = CuvisAIClient(host=host, port=port)
    client.channel, client.stub = MagicMock(), MagicMock()
    client._connected, client.session_id = True, "s1"
    return client


def _assert_dropped_without_close_session(client):
    """The client's channel is closed locally; nothing went to its stopped server."""
    client.channel.close.assert_called_once()
    client.stub.CloseSession.assert_not_called()
    assert not client._connected


@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ServerManager")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=True)
def test_reconnect_skips_starting_a_server_that_already_listens(
    mock_is_listening, mock_dialog_cls, mock_manager_cls, mock_client_cls, qtbot
):
    window = MainWindow()
    qtbot.addWidget(window)

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings()

    window._show_connection_dialog()

    mock_is_listening.assert_called_once_with("localhost", 50051)
    mock_manager_cls.assert_not_called()
    assert window.server_manager is None


@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ServerManager")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=False)
def test_reconnect_starts_a_server_when_none_is_listening(
    mock_is_listening, mock_dialog_cls, mock_manager_cls, mock_client_cls, qtbot
):
    window = MainWindow()
    qtbot.addWidget(window)

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings()

    manager = mock_manager_cls.return_value
    manager.wait_ready.return_value = True

    window._show_connection_dialog()

    mock_manager_cls.assert_called_once_with(port=50051)
    manager.start.assert_called_once()
    manager.wait_ready.assert_called_once()
    from cuvis_ai_ui.server import SERVER_READY_TIMEOUT

    assert manager.wait_ready.call_args.kwargs["timeout"] == SERVER_READY_TIMEOUT
    assert window.server_manager is manager


@patch("cuvis_ai_ui.main_window.QMessageBox")
@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ServerManager")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=False)
def test_reconnect_shows_the_manager_error_when_the_server_is_not_ready(
    mock_is_listening, mock_dialog_cls, mock_manager_cls, mock_client_cls, mock_messagebox, qtbot
):
    window = MainWindow()
    qtbot.addWidget(window)

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings()

    manager = mock_manager_cls.return_value
    manager.wait_ready.return_value = False
    manager.last_error = "the server process exited"

    window._show_connection_dialog()

    warning_call = mock_messagebox.warning.call_args
    assert "the server process exited" in warning_call.args[2]


@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ServerManager")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=False)
def test_reconnect_locally_stops_the_server_this_window_already_owns(
    mock_is_listening, mock_dialog_cls, mock_manager_cls, mock_client_cls, qtbot
):
    """Reconnecting locally to a port nothing listens on must stop the
    manager this window already started before replacing it, or the old
    server process is orphaned and keeps running until the app exits."""
    window = MainWindow()
    qtbot.addWidget(window)

    old_manager = MagicMock()
    old_manager.is_running.return_value = True
    window.set_server_manager(old_manager)

    new_manager = mock_manager_cls.return_value
    new_manager.wait_ready.return_value = True

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings(port=50052)

    window._show_connection_dialog()

    old_manager.stop.assert_called_once()
    assert window.server_manager is new_manager


@patch("cuvis_ai_ui.main_window.QMessageBox")
@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ServerManager")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=False)
def test_reconnect_waits_for_the_server_this_window_is_still_starting(
    mock_is_listening, mock_dialog_cls, mock_manager_cls, mock_client_cls, mock_messagebox, qtbot
):
    """A server this window started on the same port that is alive but not
    listening yet (a slow first start) is waited for again, not replaced by a
    second server process on that port."""
    window = MainWindow()
    qtbot.addWidget(window)

    starting = MagicMock()
    starting.port = 50051
    starting.is_running.return_value = True
    starting.wait_ready.return_value = True
    window.set_server_manager(starting)

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings(port=50051)

    window._show_connection_dialog()

    mock_manager_cls.assert_not_called()
    starting.stop.assert_not_called()
    starting.start.assert_not_called()
    starting.wait_ready.assert_called_once()
    assert window.server_manager is starting


@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ServerManager")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=True)
def test_reconnect_in_local_mode_connects_to_localhost(
    mock_is_listening, mock_dialog_cls, mock_manager_cls, mock_client_cls, qtbot
):
    """Local mode means this machine, even when the dialog still holds a remote host."""
    window = MainWindow()
    qtbot.addWidget(window)

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = {**_local_settings(), "host": "remote.example"}

    window._show_connection_dialog()

    mock_is_listening.assert_called_once_with("localhost", 50051)
    assert mock_client_cls.call_args.kwargs["host"] == "localhost"


@patch("cuvis_ai_ui.main_window.QMessageBox")
@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ServerManager")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=False)
def test_a_cancelled_server_wait_keeps_the_old_connection(
    mock_is_listening, mock_dialog_cls, mock_manager_cls, mock_client_cls, mock_messagebox, qtbot
):
    """Cancel changes nothing: the old client is neither closed (no CloseSession
    RPC that could stall) nor replaced, and no error box appears."""
    old = MagicMock()
    window = MainWindow(client=old)
    qtbot.addWidget(window)
    mock_manager_cls.return_value.wait_ready.side_effect = OperationCancelled()

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings()

    window._show_connection_dialog()

    assert window.client is old
    old.disconnect.assert_not_called()
    mock_client_cls.return_value.connect.assert_not_called()
    mock_messagebox.warning.assert_not_called()
    assert window.statusBar().currentMessage() == SERVER_WAIT_CANCELLED


@pytest.mark.parametrize("host", ["localhost", "LocalHost", "127.0.0.1", "[::1]"])
@patch("cuvis_ai_ui.main_window.QMessageBox")
@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ServerManager")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=False)
def test_a_cancelled_port_switch_drops_the_client_of_the_server_it_stopped(
    mock_is_listening,
    mock_dialog_cls,
    mock_manager_cls,
    mock_client_cls,
    mock_messagebox,
    host,
    qtbot,
):
    """Switching to another local port stops this window's server before the
    wait. Cancelling that wait must not keep a client of the stopped server
    marked connected, nor its channel open, however its host names this
    machine (a remote-mode host is typed by the user); a second cancelled
    attempt stays disconnected."""
    old = _connected_client(host=host)
    window = MainWindow(client=old)
    qtbot.addWidget(window)
    old_manager = MagicMock()
    old_manager.port = 50051
    old_manager.is_running.return_value = True
    window.set_server_manager(old_manager)

    new_manager = mock_manager_cls.return_value
    new_manager.port = 50052
    new_manager.is_running.return_value = True
    new_manager.wait_ready.side_effect = OperationCancelled()

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings(port=50052)

    window._show_connection_dialog()

    old_manager.stop.assert_called_once()
    assert window.client is None
    assert window._connection_label.text() == "Not connected"
    assert "not connected" in window.statusBar().currentMessage()

    # The second attempt waits for the server it left starting; nothing to drop.
    window._show_connection_dialog()

    assert window.client is None
    assert window._connection_label.text() == "Not connected"
    assert window.statusBar().currentMessage() == SERVER_WAIT_CANCELLED
    assert new_manager.wait_ready.call_count == 2
    _assert_dropped_without_close_session(old)
    new_manager.stop.assert_not_called()
    mock_client_cls.return_value.connect.assert_not_called()
    mock_messagebox.warning.assert_not_called()


@patch("cuvis_ai_ui.main_window.QMessageBox")
@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ServerManager")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=False)
def test_cancelled_local_starts_keep_an_unrelated_remote_connection(
    mock_is_listening, mock_dialog_cls, mock_manager_cls, mock_client_cls, mock_messagebox, qtbot
):
    """A cancelled local start leaves the remote client and this window's new
    manager side by side. Switching to another local port then stops that
    manager, which never served the remote client: cancelling again must keep
    the remote connection."""
    remote = MagicMock()
    remote.host, remote.port = "remote.example", 50051
    window = MainWindow(client=remote)
    qtbot.addWidget(window)

    manager_a, manager_b = MagicMock(), MagicMock()
    manager_a.port, manager_b.port = 50051, 50052
    for manager in (manager_a, manager_b):
        manager.is_running.return_value = True
        manager.wait_ready.side_effect = OperationCancelled()
    mock_manager_cls.side_effect = [manager_a, manager_b]

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    for port in (50051, 50052):
        dialog.get_settings.return_value = _local_settings(port=port)
        window._show_connection_dialog()

        assert window.client is remote
        assert window._connection_label.text() == "Connected"
        assert window.statusBar().currentMessage() == SERVER_WAIT_CANCELLED

    manager_a.stop.assert_called_once()
    remote.disconnect.assert_not_called()
    mock_client_cls.return_value.connect.assert_not_called()
    mock_messagebox.warning.assert_not_called()


@patch("cuvis_ai_ui.main_window.check_cancelled", side_effect=OperationCancelled())
@patch("cuvis_ai_ui.main_window.QMessageBox")
@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=True)
def test_a_connect_cancelled_before_the_old_client_closed_keeps_it(
    mock_is_listening, mock_dialog_cls, mock_client_cls, mock_messagebox, mock_check, qtbot
):
    """Cancel at the first checkpoint, before the old client's CloseSession:
    the old connection stays, still marked connected, and nothing is closed."""
    old = MagicMock()
    window = MainWindow(client=old)
    qtbot.addWidget(window)

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings()

    window._show_connection_dialog()

    assert window.client is old
    old.disconnect.assert_not_called()
    mock_client_cls.return_value.connect.assert_not_called()
    assert window._connection_label.text() == "Connected"
    assert window.statusBar().currentMessage() == "Connecting cancelled; the old connection stays."
    mock_messagebox.warning.assert_not_called()


@patch("cuvis_ai_ui.main_window.check_cancelled", side_effect=OperationCancelled())
@patch("cuvis_ai_ui.main_window.QMessageBox")
@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
def test_a_cancelled_switch_to_remote_drops_the_client_of_the_stopped_server(
    mock_dialog_cls, mock_client_cls, mock_messagebox, mock_check, qtbot
):
    """Switching to a remote server stops this window's local server first. A
    Cancel before the old client's CloseSession must not keep that client of the
    stopped server marked connected, nor its channel open; nothing is sent to the
    server that is gone."""
    old = _connected_client()
    window = MainWindow(client=old)
    qtbot.addWidget(window)
    manager = MagicMock()
    manager.port = 50051
    manager.is_running.return_value = True
    window.set_server_manager(manager)

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = {"mode": "remote", "host": "remote.example", "port": 50051}

    window._show_connection_dialog()

    manager.stop.assert_called_once()
    assert window.client is None
    assert window._connection_label.text() == "Not connected"
    assert "not connected" in window.statusBar().currentMessage()
    _assert_dropped_without_close_session(old)
    mock_client_cls.return_value.connect.assert_not_called()
    mock_messagebox.warning.assert_not_called()


@pytest.mark.parametrize("outcome", ["connected", "failed", "cancelled"])
@patch("cuvis_ai_ui.main_window.QMessageBox")
@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=True)
def test_a_port_switch_that_stopped_the_old_server_ends_like_any_reconnect(
    mock_is_listening, mock_dialog_cls, mock_client_cls, mock_messagebox, outcome, qtbot
):
    """Once past the first checkpoint, a switch that stopped the old client's
    server ends as every reconnect does: the new client, or no client with the
    error box or the cancel note."""
    old = MagicMock()
    old.host, old.port = "localhost", 50051
    window = MainWindow(client=old)
    qtbot.addWidget(window)
    manager = MagicMock()
    manager.port = 50051
    manager.is_running.return_value = True
    window.set_server_manager(manager)
    new = mock_client_cls.return_value
    if outcome == "failed":
        new.connect.side_effect = ConnectionError("handshake refused")
    elif outcome == "cancelled":
        new.connect.side_effect = OperationCancelled()

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings(port=50052)

    window._show_connection_dialog()

    manager.stop.assert_called_once()
    old.disconnect.assert_called_once()
    if outcome == "connected":
        assert window.client is new
        assert window._connection_label.text() == "Connected"
        mock_messagebox.warning.assert_not_called()
    else:
        assert window.client is None
        assert window._connection_label.text() == "Not connected"
    if outcome == "failed":
        assert "handshake refused" in mock_messagebox.warning.call_args.args[2]
    if outcome == "cancelled":
        assert "not connected" in window.statusBar().currentMessage()
        mock_messagebox.warning.assert_not_called()


@patch("cuvis_ai_ui.main_window.QMessageBox")
@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=True)
def test_a_connect_cancelled_after_the_old_client_closed_leaves_no_client(
    mock_is_listening, mock_dialog_cls, mock_client_cls, mock_messagebox, qtbot
):
    old = MagicMock()
    window = MainWindow(client=old)
    qtbot.addWidget(window)
    mock_client_cls.return_value.connect.side_effect = OperationCancelled()

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings()

    window._show_connection_dialog()

    old.disconnect.assert_called_once()
    assert window.client is None
    mock_messagebox.warning.assert_not_called()
    assert "not connected" in window.statusBar().currentMessage()


@patch("cuvis_ai_ui.main_window.QMessageBox")
@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=True)
def test_a_failed_reconnect_names_the_error_and_leaves_no_client(
    mock_is_listening, mock_dialog_cls, mock_client_cls, mock_messagebox, qtbot
):
    window = MainWindow(client=MagicMock())
    qtbot.addWidget(window)
    mock_client_cls.return_value.connect.side_effect = ConnectionError("handshake refused")

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings()

    window._show_connection_dialog()

    assert window.client is None
    assert "handshake refused" in mock_messagebox.warning.call_args.args[2]


@patch("cuvis_ai_ui.main_window.CuvisAIClient")
@patch("cuvis_ai_ui.main_window.ConnectionDialog")
@patch("cuvis_ai_ui.main_window.is_listening", return_value=True)
def test_reconnect_hands_the_stop_event_to_connect(
    mock_is_listening, mock_dialog_cls, mock_client_cls, qtbot
):
    window = MainWindow()
    qtbot.addWidget(window)
    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = True
    dialog.get_settings.return_value = _local_settings()

    window._show_connection_dialog()

    assert window.client is mock_client_cls.return_value
    stop = mock_client_cls.return_value.connect.call_args.kwargs["stop"]
    assert isinstance(stop, threading.Event)
