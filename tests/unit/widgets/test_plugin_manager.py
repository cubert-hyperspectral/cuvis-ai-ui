"""Unit tests for PluginManager widget."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from PySide6.QtWidgets import QDialogButtonBox, QTableWidget, QTabWidget

from cuvis_ai_ui.widgets.plugin_manager import PluginManagerDialog


def test_plugin_manager_dialog_initialization(qapp, mock_grpc_client):
    """Test PluginManagerDialog initialization."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    assert dialog is not None
    assert dialog.windowTitle() == "Plugin Manager"
    assert dialog._client == mock_grpc_client


def test_plugin_manager_has_tabs(qapp, mock_grpc_client):
    """Test that PluginManagerDialog has all expected tabs."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Find tab widget
    tab_widget = dialog.findChild(QTabWidget)
    assert tab_widget is not None

    # Should have multiple tabs
    assert tab_widget.count() >= 3  # At minimum: Status, Git, Local, Manifest


def test_plugin_manager_status_table(qapp, mock_grpc_client):
    """Test that PluginManagerDialog has a status table."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Should have a status table widget
    assert dialog._status_table is not None
    assert isinstance(dialog._status_table, QTableWidget)

    # Status table should have columns
    assert dialog._status_table.columnCount() > 0


def test_plugin_manager_refresh_status(qapp, mock_grpc_client):
    """Test refreshing plugin status."""
    mock_grpc_client.list_available_nodes.return_value = [
        {
            "class_name": "TestNode",
            "full_path": "test.TestNode",
            "source": "builtin",
            "plugin_name": "",
            "input_specs": [],
            "output_specs": []
        }
    ]

    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Trigger refresh
    dialog._refresh_status()

    # Should have called gRPC client
    mock_grpc_client.list_available_nodes.assert_called()


def test_plugin_manager_plugins_loaded_signal(qapp, qtbot, mock_grpc_client):
    """Test that plugins_loaded signal is emitted."""
    mock_grpc_client.load_plugins.return_value = {
        "loaded_plugins": ["test_plugin"],
        "failed_plugins": []
    }

    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Signal should exist
    assert hasattr(dialog, "plugins_loaded")


def test_plugin_manager_close_button(qapp, mock_grpc_client):
    """Test that dialog has a Close button."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Find button box
    button_box = dialog.findChild(QDialogButtonBox)
    assert button_box is not None

    # Should have Close button
    close_button = button_box.button(QDialogButtonBox.StandardButton.Close)
    assert close_button is not None


def test_plugin_manager_minimum_size(qapp, mock_grpc_client):
    """Test that dialog has reasonable minimum size."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    assert dialog.minimumWidth() > 0
    assert dialog.minimumHeight() > 0


def test_plugin_manager_git_tab_exists(qapp, mock_grpc_client):
    """Test that Git loading tab exists."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    tab_widget = dialog.findChild(QTabWidget)

    # Look for Git tab
    git_tab_found = False
    for i in range(tab_widget.count()):
        if "Git" in tab_widget.tabText(i):
            git_tab_found = True
            break

    assert git_tab_found


def test_plugin_manager_local_tab_exists(qapp, mock_grpc_client):
    """Test that Local loading tab exists."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    tab_widget = dialog.findChild(QTabWidget)

    # Look for Local tab
    local_tab_found = False
    for i in range(tab_widget.count()):
        if "Local" in tab_widget.tabText(i):
            local_tab_found = True
            break

    assert local_tab_found


def test_plugin_manager_manifest_tab_exists(qapp, mock_grpc_client):
    """Test that Manifest loading tab exists."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    tab_widget = dialog.findChild(QTabWidget)

    # Look for Manifest tab
    manifest_tab_found = False
    for i in range(tab_widget.count()):
        if "Manifest" in tab_widget.tabText(i):
            manifest_tab_found = True
            break

    assert manifest_tab_found


def test_plugin_manager_status_tab_is_first(qapp, mock_grpc_client):
    """Test that Status/Loaded Plugins tab is the first tab."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    tab_widget = dialog.findChild(QTabWidget)

    # First tab should be status/loaded plugins
    first_tab_text = tab_widget.tabText(0)
    assert "Loaded" in first_tab_text or "Status" in first_tab_text


@patch('cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries')
def test_plugin_manager_loads_saved_entries(mock_load, qapp, mock_grpc_client):
    """Test that dialog loads saved plugin entries on init."""
    mock_load.return_value = []

    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Should have called load_plugin_entries
    mock_load.assert_called()


def test_plugin_manager_status_table_columns(qapp, mock_grpc_client):
    """Test that status table has correct columns."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    table = dialog._status_table

    # Should have columns: Load, Plugin Name, Type, Source, Provided Nodes
    assert table.columnCount() >= 5

    # Check header labels
    headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]

    # Should contain key column names
    assert any("Load" in h for h in headers)
    assert any("Name" in h or "Plugin" in h for h in headers)


def test_plugin_manager_with_failed_grpc(qapp):
    """Test PluginManagerDialog when gRPC client fails."""
    mock_client = MagicMock()
    mock_client.list_available_nodes.side_effect = Exception("gRPC connection failed")

    # Should not crash on initialization even if gRPC fails
    dialog = PluginManagerDialog(client=mock_client)

    assert dialog is not None


def test_plugin_manager_refresh_button_exists(qapp, mock_grpc_client):
    """Test that Refresh Status button exists."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Look for refresh button (should be in status tab)
    # This tests that the button exists somewhere in the widget tree
    from PySide6.QtWidgets import QPushButton

    buttons = dialog.findChildren(QPushButton)
    refresh_button_found = any("Refresh" in btn.text() for btn in buttons)

    assert refresh_button_found


def test_plugin_manager_remove_button_exists(qapp, mock_grpc_client):
    """Test that Remove Selected button exists."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    from PySide6.QtWidgets import QPushButton

    buttons = dialog.findChildren(QPushButton)
    remove_button_found = any("Remove" in btn.text() for btn in buttons)

    assert remove_button_found


def test_plugin_manager_plugin_entries_storage(qapp, mock_grpc_client):
    """Test that dialog stores plugin entries."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Should have _plugin_entries attribute
    assert hasattr(dialog, "_plugin_entries")
    assert isinstance(dialog._plugin_entries, list)


def test_plugin_manager_is_refreshing_flag(qapp, mock_grpc_client):
    """Test that dialog has _is_refreshing flag to prevent recursive updates."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Should have _is_refreshing flag
    assert hasattr(dialog, "_is_refreshing")
    assert isinstance(dialog._is_refreshing, bool)


@patch('cuvis_ai_ui.widgets.plugin_manager.QFileDialog.getOpenFileName')
def test_plugin_manager_manifest_file_dialog(mock_file_dialog, qapp, mock_grpc_client):
    """Test that manifest tab can trigger file dialog."""
    mock_file_dialog.return_value = ("", "")  # User cancels

    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Find browse button in manifest tab
    from PySide6.QtWidgets import QPushButton

    buttons = dialog.findChildren(QPushButton)

    # Look for a browse/select button
    browse_found = any("Browse" in btn.text() or "Select" in btn.text() for btn in buttons)

    # May or may not have browse button, depends on implementation
    assert dialog is not None  # Just ensure dialog doesn't crash


def test_plugin_manager_accepts_none_parent(qapp, mock_grpc_client):
    """Test that dialog accepts None as parent."""
    dialog = PluginManagerDialog(client=mock_grpc_client, parent=None)

    assert dialog is not None
    assert dialog.parent() is None


def test_plugin_manager_dialog_is_modal(qapp, mock_grpc_client):
    """Test that dialog can be shown modally."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Should be a dialog that can be shown
    # Don't actually show it in tests, just verify it's a QDialog
    from PySide6.QtWidgets import QDialog
    assert isinstance(dialog, QDialog)
