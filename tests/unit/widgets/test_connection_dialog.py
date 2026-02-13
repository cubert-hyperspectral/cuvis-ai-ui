"""Unit tests for ConnectionDialog widget."""

import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import (
    QDialogButtonBox,
    QGroupBox,
    QLineEdit,
    QRadioButton,
    QSpinBox,
)

from cuvis_ai_ui.widgets.connection_dialog import ConnectionDialog

# ---------------------------------------------------------------------------
# Default settings used by all tests (monkeypatched)
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "version": 1,
    "mode": "local",
    "host": "localhost",
    "port": 50051,
    "auto_start": True,
}

REMOTE_SETTINGS = {
    "version": 1,
    "mode": "remote",
    "host": "192.168.1.100",
    "port": 9999,
    "auto_start": False,
}


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch):
    """Monkeypatch load/save/get_default so the dialog never touches disk."""
    monkeypatch.setattr(
        "cuvis_ai_ui.widgets.connection_dialog.load_connection_settings",
        lambda: dict(DEFAULT_SETTINGS),
    )
    monkeypatch.setattr(
        "cuvis_ai_ui.widgets.connection_dialog.save_connection_settings",
        lambda s: None,
    )
    monkeypatch.setattr(
        "cuvis_ai_ui.widgets.connection_dialog.get_default_connection_settings",
        lambda: dict(DEFAULT_SETTINGS),
    )


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------


def test_dialog_initialization_creates_widgets(qapp):
    """Test that dialog creates expected widgets on initialization."""
    dialog = ConnectionDialog()

    assert dialog.windowTitle() == "Server Connection"
    assert dialog.minimumWidth() >= 420

    # Radio buttons
    assert hasattr(dialog, "_local_radio")
    assert hasattr(dialog, "_remote_radio")
    assert isinstance(dialog._local_radio, QRadioButton)
    assert isinstance(dialog._remote_radio, QRadioButton)

    # Group boxes
    assert hasattr(dialog, "_local_group")
    assert hasattr(dialog, "_remote_group")
    assert isinstance(dialog._local_group, QGroupBox)
    assert isinstance(dialog._remote_group, QGroupBox)

    # Spinboxes and line edits
    assert isinstance(dialog._local_port, QSpinBox)
    assert isinstance(dialog._remote_port, QSpinBox)
    assert isinstance(dialog._remote_host, QLineEdit)


def test_dialog_loads_default_local_mode(qapp):
    """Test that dialog starts in local mode with default settings."""
    dialog = ConnectionDialog()

    assert dialog._local_radio.isChecked() is True
    assert dialog._remote_radio.isChecked() is False
    assert dialog._local_port.value() == 50051
    assert dialog._remote_host.text() == "localhost"
    assert dialog._remote_port.value() == 50051


def test_dialog_loads_remote_mode(qapp, monkeypatch):
    """Test that dialog starts in remote mode when settings say remote."""
    monkeypatch.setattr(
        "cuvis_ai_ui.widgets.connection_dialog.load_connection_settings",
        lambda: dict(REMOTE_SETTINGS),
    )

    dialog = ConnectionDialog()

    assert dialog._remote_radio.isChecked() is True
    assert dialog._local_radio.isChecked() is False
    assert dialog._remote_host.text() == "192.168.1.100"
    assert dialog._remote_port.value() == 9999


# ---------------------------------------------------------------------------
# Mode toggle tests
# ---------------------------------------------------------------------------


def test_mode_toggle_local_enables_local_group(qapp):
    """Test that selecting local mode enables local group and disables remote."""
    dialog = ConnectionDialog()

    dialog._local_radio.setChecked(True)

    assert dialog._local_group.isEnabled() is True
    assert dialog._remote_group.isEnabled() is False


def test_mode_toggle_remote_enables_remote_group(qapp):
    """Test that selecting remote mode enables remote group and disables local."""
    dialog = ConnectionDialog()

    dialog._remote_radio.setChecked(True)

    assert dialog._local_group.isEnabled() is False
    assert dialog._remote_group.isEnabled() is True


def test_mode_toggle_clears_test_status(qapp):
    """Test that toggling mode clears the test connection status label."""
    dialog = ConnectionDialog()
    dialog._test_status.setText("Connected")

    dialog._remote_radio.setChecked(True)

    assert dialog._test_status.text() == ""


# ---------------------------------------------------------------------------
# get_settings() tests
# ---------------------------------------------------------------------------


def test_get_settings_local_mode(qapp):
    """Test get_settings returns correct dict for local mode."""
    dialog = ConnectionDialog()

    dialog._local_radio.setChecked(True)
    dialog._local_port.setValue(12345)

    settings = dialog.get_settings()

    assert settings["mode"] == "local"
    assert settings["host"] == "localhost"
    assert settings["port"] == 12345
    assert settings["auto_start"] is True


def test_get_settings_remote_mode(qapp):
    """Test get_settings returns correct dict for remote mode."""
    dialog = ConnectionDialog()

    dialog._remote_radio.setChecked(True)
    dialog._remote_host.setText("10.0.0.5")
    dialog._remote_port.setValue(8080)

    settings = dialog.get_settings()

    assert settings["mode"] == "remote"
    assert settings["host"] == "10.0.0.5"
    assert settings["port"] == 8080
    assert settings["auto_start"] is False


def test_get_settings_remote_mode_empty_host_defaults_to_localhost(qapp):
    """Test that an empty remote host defaults to localhost."""
    dialog = ConnectionDialog()

    dialog._remote_radio.setChecked(True)
    dialog._remote_host.setText("   ")
    dialog._remote_port.setValue(50051)

    settings = dialog.get_settings()

    assert settings["host"] == "localhost"


# ---------------------------------------------------------------------------
# Restore defaults tests
# ---------------------------------------------------------------------------


def test_restore_defaults_resets_to_local(qapp):
    """Test that restore defaults resets mode to local."""
    dialog = ConnectionDialog()

    # Switch to remote first
    dialog._remote_radio.setChecked(True)
    dialog._remote_host.setText("10.0.0.99")
    dialog._remote_port.setValue(9999)

    # Restore defaults
    dialog._restore_defaults()

    assert dialog._local_radio.isChecked() is True
    assert dialog._local_port.value() == 50051
    assert dialog._remote_host.text() == "localhost"


def test_restore_defaults_resets_port(qapp):
    """Test that restore defaults resets port to default value."""
    dialog = ConnectionDialog()

    dialog._local_port.setValue(9999)

    dialog._restore_defaults()

    assert dialog._local_port.value() == 50051


# ---------------------------------------------------------------------------
# _on_accept tests
# ---------------------------------------------------------------------------


def test_on_accept_saves_settings(qapp, monkeypatch):
    """Test that _on_accept saves the current settings."""
    saved = {}

    def capture_save(s):
        saved.update(s)

    monkeypatch.setattr(
        "cuvis_ai_ui.widgets.connection_dialog.save_connection_settings",
        capture_save,
    )

    dialog = ConnectionDialog()
    dialog._local_port.setValue(11111)

    # Manually call _on_accept (don't use accept() which would close and
    # potentially cause issues in test)
    dialog._on_accept()

    assert saved["mode"] == "local"
    assert saved["port"] == 11111


def test_on_accept_saves_remote_settings(qapp, monkeypatch):
    """Test that _on_accept saves remote settings correctly."""
    saved = {}

    def capture_save(s):
        saved.update(s)

    monkeypatch.setattr(
        "cuvis_ai_ui.widgets.connection_dialog.save_connection_settings",
        capture_save,
    )

    dialog = ConnectionDialog()
    dialog._remote_radio.setChecked(True)
    dialog._remote_host.setText("myhost")
    dialog._remote_port.setValue(22222)

    dialog._on_accept()

    assert saved["mode"] == "remote"
    assert saved["host"] == "myhost"
    assert saved["port"] == 22222
    assert saved["auto_start"] is False


# ---------------------------------------------------------------------------
# _test_connection tests
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.widgets.connection_dialog.grpc")
def test_test_connection_success(mock_grpc, qapp):
    """Test _test_connection when server is reachable."""
    mock_future = MagicMock()
    mock_future.result.return_value = None  # No exception = success
    mock_grpc.channel_ready_future.return_value = mock_future
    mock_channel = MagicMock()
    mock_grpc.insecure_channel.return_value = mock_channel

    dialog = ConnectionDialog()
    dialog._test_connection()

    assert dialog._test_status.text() == "Connected"
    assert "green" in dialog._test_status.styleSheet()
    assert dialog._test_btn.isEnabled() is True


@patch("cuvis_ai_ui.widgets.connection_dialog.grpc")
def test_test_connection_failure(mock_grpc, qapp):
    """Test _test_connection when server is unreachable."""
    mock_future = MagicMock()
    mock_future.result.side_effect = Exception("timeout")
    mock_grpc.channel_ready_future.return_value = mock_future
    mock_grpc.insecure_channel.return_value = MagicMock()

    dialog = ConnectionDialog()
    dialog._test_connection()

    assert dialog._test_status.text() == "Failed"
    assert "red" in dialog._test_status.styleSheet()
    assert dialog._test_btn.isEnabled() is True


# ---------------------------------------------------------------------------
# Spinbox range validation tests
# ---------------------------------------------------------------------------


def test_local_port_range(qapp):
    """Test that local port spinbox has correct range."""
    dialog = ConnectionDialog()

    assert dialog._local_port.minimum() == 1024
    assert dialog._local_port.maximum() == 65535


def test_remote_port_range(qapp):
    """Test that remote port spinbox has correct range."""
    dialog = ConnectionDialog()

    assert dialog._remote_port.minimum() == 1
    assert dialog._remote_port.maximum() == 65535


# ---------------------------------------------------------------------------
# Button box tests
# ---------------------------------------------------------------------------


def test_dialog_has_ok_cancel_restore_buttons(qapp):
    """Test that dialog has Ok, Cancel, and RestoreDefaults buttons."""
    dialog = ConnectionDialog()

    btn_box = dialog.findChild(QDialogButtonBox)
    assert btn_box is not None

    ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
    cancel_btn = btn_box.button(QDialogButtonBox.StandardButton.Cancel)
    restore_btn = btn_box.button(QDialogButtonBox.StandardButton.RestoreDefaults)

    assert ok_btn is not None
    assert cancel_btn is not None
    assert restore_btn is not None


def test_dialog_test_connection_button_exists(qapp):
    """Test that the Test Connection button exists."""
    dialog = ConnectionDialog()

    assert hasattr(dialog, "_test_btn")
    assert dialog._test_btn.text() == "Test Connection"
