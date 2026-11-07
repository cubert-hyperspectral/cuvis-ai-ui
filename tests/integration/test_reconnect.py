"""Reconnecting through Tools > Connect to Server in local mode."""

from unittest.mock import patch

from cuvis_ai_ui.main_window import MainWindow


def _local_settings(port=50051):
    return {"mode": "local", "host": "localhost", "port": port, "auto_start": True}


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
