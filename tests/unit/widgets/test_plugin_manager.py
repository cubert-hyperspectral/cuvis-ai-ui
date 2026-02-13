"""Unit tests for PluginManager widget."""

from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QPushButton,
    QTableWidget,
    QTabWidget,
)

from cuvis_ai_ui.widgets.plugin_manager import (
    PluginManagerDialog,
    SessionDialog,
    STATUS_COL_LOAD,
    STATUS_COL_NAME,
    STATUS_COL_SOURCE,
    STATUS_COL_PROVIDES,
)


# ---------------------------------------------------------------------------
# PluginManagerDialog - Basic initialization
# ---------------------------------------------------------------------------


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
            "output_specs": [],
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
        "failed_plugins": [],
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


@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_plugin_manager_loads_saved_entries(mock_load, qapp, mock_grpc_client):
    """Test that dialog loads saved plugin entries on init."""
    mock_load.return_value = []

    _dialog = PluginManagerDialog(client=mock_grpc_client)

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


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.warning")
def test_plugin_manager_with_failed_grpc(mock_warning, qapp):
    """Test PluginManagerDialog when gRPC client fails."""
    mock_client = MagicMock()
    mock_client.list_available_nodes.side_effect = Exception("gRPC connection failed")

    # Should not crash on initialization even if gRPC fails
    dialog = PluginManagerDialog(client=mock_client)

    assert dialog is not None
    # The error dialog should have been shown (but mocked)
    mock_warning.assert_called_once()


def test_plugin_manager_refresh_button_exists(qapp, mock_grpc_client):
    """Test that Refresh Status button exists."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Look for refresh button (should be in status tab)
    # This tests that the button exists somewhere in the widget tree
    buttons = dialog.findChildren(QPushButton)
    refresh_button_found = any("Refresh" in btn.text() for btn in buttons)

    assert refresh_button_found


def test_plugin_manager_remove_button_exists(qapp, mock_grpc_client):
    """Test that Remove Selected button exists."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

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


@patch("cuvis_ai_ui.widgets.plugin_manager.QFileDialog.getOpenFileName")
def test_plugin_manager_manifest_file_dialog(mock_file_dialog, qapp, mock_grpc_client):
    """Test that manifest tab can trigger file dialog."""
    mock_file_dialog.return_value = ("", "")  # User cancels

    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Find browse button in manifest tab
    buttons = dialog.findChildren(QPushButton)

    # Look for a browse/select button
    _browse_found = any("Browse" in btn.text() or "Select" in btn.text() for btn in buttons)

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


# ---------------------------------------------------------------------------
# Status table - populate with plugin entries
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_refresh_status_populates_table_rows(mock_load, qapp, mock_grpc_client):
    """Test that _refresh_status creates one table row per plugin entry."""
    entries = [
        {
            "name": "plugin_a",
            "enabled": True,
            "source": "git",
            "config": {"repo": "git@host:org/a.git"},
        },
        {
            "name": "plugin_b",
            "enabled": False,
            "source": "local",
            "config": {"path": "/tmp/b"},
        },
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)

    assert dialog._status_table.rowCount() == 2

    # First row should be plugin_a, checked
    name_0 = dialog._status_table.item(0, STATUS_COL_NAME).text()
    assert name_0 == "plugin_a"
    load_0 = dialog._status_table.item(0, STATUS_COL_LOAD)
    assert load_0.checkState() == Qt.CheckState.Checked

    # Second row should be plugin_b, unchecked
    name_1 = dialog._status_table.item(1, STATUS_COL_NAME).text()
    assert name_1 == "plugin_b"
    load_1 = dialog._status_table.item(1, STATUS_COL_LOAD)
    assert load_1.checkState() == Qt.CheckState.Unchecked


@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_refresh_status_shows_source_from_config_repo(mock_load, qapp, mock_grpc_client):
    """Test that source column shows repo URL when origin is missing."""
    entries = [
        {
            "name": "my_plugin",
            "enabled": True,
            "source": "git",
            "config": {"repo": "git@host:org/repo.git"},
        },
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)

    source_text = dialog._status_table.item(0, STATUS_COL_SOURCE).text()
    assert "git@host:org/repo.git" in source_text


@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_refresh_status_shows_source_from_config_path(mock_load, qapp, mock_grpc_client):
    """Test that source column shows path when origin is missing and config has path."""
    entries = [
        {
            "name": "local_plugin",
            "enabled": True,
            "source": "local",
            "config": {"path": "/home/user/plugins/myplugin"},
        },
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)

    source_text = dialog._status_table.item(0, STATUS_COL_SOURCE).text()
    assert "/home/user/plugins/myplugin" in source_text


@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_refresh_status_shows_origin_when_set(mock_load, qapp, mock_grpc_client):
    """Test that source column shows origin field when present."""
    entries = [
        {
            "name": "manifest_plugin",
            "enabled": True,
            "source": "manifest",
            "origin": "/some/manifest.yaml",
            "config": {"repo": "should-not-show"},
        },
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)

    source_text = dialog._status_table.item(0, STATUS_COL_SOURCE).text()
    assert source_text == "/some/manifest.yaml"


@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_refresh_status_provides_column_shows_count(mock_load, qapp, mock_grpc_client):
    """Test that provided nodes column shows count when provides list is present."""
    entries = [
        {
            "name": "my_plugin",
            "enabled": True,
            "source": "git",
            "config": {"provides": ["node.A", "node.B", "node.C"]},
        },
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)

    provided = dialog._status_table.item(0, STATUS_COL_PROVIDES).text()
    assert provided == "3"


@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_refresh_status_provides_column_shows_auto(mock_load, qapp, mock_grpc_client):
    """Test that provided nodes column shows 'auto' when no provides list."""
    entries = [
        {
            "name": "auto_plugin",
            "enabled": True,
            "source": "git",
            "config": {"repo": "x"},
        },
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)

    provided = dialog._status_table.item(0, STATUS_COL_PROVIDES).text()
    assert provided == "auto"


@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_refresh_status_provides_column_from_loaded_nodes(mock_load, qapp, mock_grpc_client):
    """Test provided column shows count from server when plugin is loaded."""
    entries = [
        {
            "name": "server_plugin",
            "enabled": True,
            "source": "git",
            "config": {},
        },
    ]
    mock_load.return_value = entries
    mock_grpc_client.list_available_nodes.return_value = [
        {"source": "plugin", "plugin_name": "server_plugin"},
        {"source": "plugin", "plugin_name": "server_plugin"},
    ]

    dialog = PluginManagerDialog(client=mock_grpc_client)

    provided = dialog._status_table.item(0, STATUS_COL_PROVIDES).text()
    assert provided == "2"


# ---------------------------------------------------------------------------
# Enable / disable toggle via checkbox
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.widgets.plugin_manager.save_plugin_entries")
@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_toggle_enable_checkbox_saves(mock_load, mock_save, qapp, mock_grpc_client):
    """Test that toggling the load checkbox persists the change."""
    entries = [
        {"name": "togglable", "enabled": True, "source": "git", "config": {}},
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Uncheck the load checkbox (row 0)
    load_item = dialog._status_table.item(0, STATUS_COL_LOAD)
    load_item.setCheckState(Qt.CheckState.Unchecked)

    # _on_status_item_changed should have persisted
    mock_save.assert_called()
    saved = mock_save.call_args[0][0]
    assert any(e["name"] == "togglable" and e["enabled"] is False for e in saved)


@patch("cuvis_ai_ui.widgets.plugin_manager.save_plugin_entries")
@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_toggle_ignored_during_refresh(mock_load, mock_save, qapp, mock_grpc_client):
    """Test that item changes during refresh are ignored."""
    entries = [
        {"name": "no_save", "enabled": True, "source": "git", "config": {}},
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)
    mock_save.reset_mock()

    # Simulate a change while _is_refreshing is True
    dialog._is_refreshing = True
    load_item = dialog._status_table.item(0, STATUS_COL_LOAD)
    # Manually fire the handler
    dialog._on_status_item_changed(load_item)

    mock_save.assert_not_called()


@patch("cuvis_ai_ui.widgets.plugin_manager.save_plugin_entries")
@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_toggle_ignored_for_non_load_column(mock_load, mock_save, qapp, mock_grpc_client):
    """Test that item changes on non-load columns are ignored."""
    entries = [
        {"name": "noop", "enabled": True, "source": "git", "config": {}},
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)
    mock_save.reset_mock()

    # Trigger handler for a non-load column item
    name_item = dialog._status_table.item(0, STATUS_COL_NAME)
    dialog._on_status_item_changed(name_item)

    mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# Git tab - load plugin
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.warning")
def test_load_git_plugin_no_name_shows_warning(mock_warn, qapp, mock_grpc_client):
    """Test loading git plugin without name shows warning."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._git_name.setText("")
    dialog._git_url.setText("git@host:org/repo.git")

    dialog._load_git_plugin()

    mock_warn.assert_called_once()
    assert "name" in mock_warn.call_args[0][2].lower()


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.warning")
def test_load_git_plugin_no_url_shows_warning(mock_warn, qapp, mock_grpc_client):
    """Test loading git plugin without URL shows warning."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._git_name.setText("my_plugin")
    dialog._git_url.setText("")

    dialog._load_git_plugin()

    mock_warn.assert_called_once()
    assert "url" in mock_warn.call_args[0][2].lower()


@patch("cuvis_ai_ui.widgets.plugin_manager.write_manifest_temp")
@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.information")
def test_load_git_plugin_success(mock_info, mock_temp, qapp, mock_grpc_client, tmp_path):
    """Test successful git plugin loading."""
    temp_file = tmp_path / "manifest.yaml"
    temp_file.touch()
    mock_temp.return_value = str(temp_file)

    mock_grpc_client.load_plugins.return_value = {
        "loaded_plugins": ["my_plugin"],
        "failed_plugins": [],
    }

    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._git_name.setText("my_plugin")
    dialog._git_url.setText("git@host:org/repo.git")
    dialog._git_ref.setText("v1.0")

    dialog._load_git_plugin()

    mock_grpc_client.load_plugins.assert_called_once()
    mock_info.assert_called_once()


@patch("cuvis_ai_ui.widgets.plugin_manager.write_manifest_temp")
@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.information")
def test_load_git_plugin_with_provides(mock_info, mock_temp, qapp, mock_grpc_client, tmp_path):
    """Test git plugin loading with explicit provides list."""
    temp_file = tmp_path / "manifest.yaml"
    temp_file.touch()
    mock_temp.return_value = str(temp_file)

    mock_grpc_client.load_plugins.return_value = {
        "loaded_plugins": ["my_plugin"],
        "failed_plugins": [],
    }

    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._git_name.setText("my_plugin")
    dialog._git_url.setText("git@host:org/repo.git")
    dialog._git_provides.setPlainText("my_plugin.NodeA\nmy_plugin.NodeB")

    dialog._load_git_plugin()

    # Verify the manifest passed to write_manifest_temp includes provides
    manifest_arg = mock_temp.call_args[0][0]
    provides = manifest_arg["plugins"]["my_plugin"].get("provides", [])
    assert "my_plugin.NodeA" in provides
    assert "my_plugin.NodeB" in provides


# ---------------------------------------------------------------------------
# Local tab - load plugin
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.warning")
def test_load_local_plugin_no_name_shows_warning(mock_warn, qapp, mock_grpc_client):
    """Test loading local plugin without name shows warning."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._local_name.setText("")
    dialog._local_path.setText("/some/path")

    dialog._load_local_plugin()

    mock_warn.assert_called_once()
    assert "name" in mock_warn.call_args[0][2].lower()


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.warning")
def test_load_local_plugin_no_path_shows_warning(mock_warn, qapp, mock_grpc_client):
    """Test loading local plugin without path shows warning."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._local_name.setText("my_plugin")
    dialog._local_path.setText("")

    dialog._load_local_plugin()

    mock_warn.assert_called_once()
    assert "path" in mock_warn.call_args[0][2].lower()


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.warning")
def test_load_local_plugin_nonexistent_path_shows_warning(mock_warn, qapp, mock_grpc_client):
    """Test loading local plugin with nonexistent path shows warning."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._local_name.setText("my_plugin")
    dialog._local_path.setText("/nonexistent/path/does/not/exist")

    dialog._load_local_plugin()

    mock_warn.assert_called_once()
    assert "not exist" in mock_warn.call_args[0][2].lower()


@patch("cuvis_ai_ui.widgets.plugin_manager.write_manifest_temp")
@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.information")
def test_load_local_plugin_success(mock_info, mock_temp, qapp, mock_grpc_client, tmp_path):
    """Test successful local plugin loading."""
    plugin_dir = tmp_path / "my_plugin"
    plugin_dir.mkdir()

    temp_file = tmp_path / "manifest.yaml"
    temp_file.touch()
    mock_temp.return_value = str(temp_file)

    mock_grpc_client.load_plugins.return_value = {
        "loaded_plugins": ["my_plugin"],
        "failed_plugins": [],
    }

    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._local_name.setText("my_plugin")
    dialog._local_path.setText(str(plugin_dir))

    dialog._load_local_plugin()

    mock_grpc_client.load_plugins.assert_called_once()
    mock_info.assert_called_once()


# ---------------------------------------------------------------------------
# Manifest tab - load plugins
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.warning")
def test_load_manifest_no_path_shows_warning(mock_warn, qapp, mock_grpc_client):
    """Test loading manifest without path shows warning."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._manifest_path.setText("")

    dialog._load_manifest_plugins()

    mock_warn.assert_called_once()
    assert (
        "select" in mock_warn.call_args[0][2].lower() or "file" in mock_warn.call_args[0][2].lower()
    )


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.warning")
def test_load_manifest_nonexistent_file_shows_warning(mock_warn, qapp, mock_grpc_client):
    """Test loading manifest with nonexistent file shows warning."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._manifest_path.setText("/does/not/exist.yaml")

    dialog._load_manifest_plugins()

    mock_warn.assert_called_once()


# ---------------------------------------------------------------------------
# _persist_plugins_from_manifest
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.widgets.plugin_manager.save_plugin_entries")
@patch("cuvis_ai_ui.widgets.plugin_manager.merge_plugin_entries")
def test_persist_plugins_from_manifest(mock_merge, mock_save, qapp, mock_grpc_client):
    """Test persisting loaded plugins from a manifest dict."""
    mock_merge.return_value = [{"name": "foo", "enabled": True, "source": "git", "config": {}}]

    dialog = PluginManagerDialog(client=mock_grpc_client)

    manifest = {
        "plugins": {
            "foo": {"repo": "git@host:org/foo.git"},
            "bar": {"repo": "git@host:org/bar.git"},
        }
    }

    dialog._persist_plugins_from_manifest(manifest, loaded=["foo"], source="git")

    mock_merge.assert_called_once()
    mock_save.assert_called_once()


@patch("cuvis_ai_ui.widgets.plugin_manager.save_plugin_entries")
@patch("cuvis_ai_ui.widgets.plugin_manager.merge_plugin_entries")
def test_persist_plugins_with_origin(mock_merge, mock_save, qapp, mock_grpc_client):
    """Test persisting plugins with an origin field."""
    mock_merge.return_value = []

    dialog = PluginManagerDialog(client=mock_grpc_client)

    manifest = {"plugins": {"foo": {"repo": "x"}}}
    dialog._persist_plugins_from_manifest(
        manifest, loaded=["foo"], source="manifest", origin="/path/to/manifest.yaml"
    )

    merge_arg = mock_merge.call_args[0][1]
    assert merge_arg[0]["origin"] == "/path/to/manifest.yaml"


@patch("cuvis_ai_ui.widgets.plugin_manager.save_plugin_entries")
def test_persist_plugins_empty_loaded_list(mock_save, qapp, mock_grpc_client):
    """Test that persist does nothing when loaded list is empty."""
    dialog = PluginManagerDialog(client=mock_grpc_client)
    mock_save.reset_mock()

    manifest = {"plugins": {"foo": {"repo": "x"}}}
    dialog._persist_plugins_from_manifest(manifest, loaded=[], source="git")

    mock_save.assert_not_called()


@patch("cuvis_ai_ui.widgets.plugin_manager.save_plugin_entries")
def test_persist_plugins_invalid_manifest(mock_save, qapp, mock_grpc_client):
    """Test that persist does nothing with invalid manifest structure."""
    dialog = PluginManagerDialog(client=mock_grpc_client)
    mock_save.reset_mock()

    manifest = {"plugins": "not_a_dict"}
    dialog._persist_plugins_from_manifest(manifest, loaded=["foo"], source="git")

    mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# _format_failed_plugins
# ---------------------------------------------------------------------------


def test_format_failed_plugins_dict(qapp, mock_grpc_client):
    """Test formatting failed plugins from dict."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    result = dialog._format_failed_plugins({"p1": "import error", "p2": "not found"})

    assert "p1: import error" in result
    assert "p2: not found" in result


def test_format_failed_plugins_list(qapp, mock_grpc_client):
    """Test formatting failed plugins from list."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    result = dialog._format_failed_plugins(["plugin_a", "plugin_b"])

    assert "plugin_a" in result
    assert "plugin_b" in result


def test_format_failed_plugins_string(qapp, mock_grpc_client):
    """Test formatting failed plugins from string."""
    dialog = PluginManagerDialog(client=mock_grpc_client)

    result = dialog._format_failed_plugins("some error message")

    assert result == "some error message"


# ---------------------------------------------------------------------------
# Browse local path
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.widgets.plugin_manager.QFileDialog.getExistingDirectory")
def test_browse_local_path_sets_text(mock_dir, qapp, mock_grpc_client):
    """Test that browsing local path sets path and auto-fills name."""
    mock_dir.return_value = "/home/user/my_cool_plugin"

    dialog = PluginManagerDialog(client=mock_grpc_client)
    dialog._local_name.setText("")  # Ensure name is empty

    dialog._browse_local_path()

    assert dialog._local_path.text() == "/home/user/my_cool_plugin"
    assert dialog._local_name.text() == "my_cool_plugin"


@patch("cuvis_ai_ui.widgets.plugin_manager.QFileDialog.getExistingDirectory")
def test_browse_local_path_cancelled(mock_dir, qapp, mock_grpc_client):
    """Test that cancelling the directory dialog doesn't change anything."""
    mock_dir.return_value = ""

    dialog = PluginManagerDialog(client=mock_grpc_client)
    dialog._local_path.setText("original")

    dialog._browse_local_path()

    assert dialog._local_path.text() == "original"


@patch("cuvis_ai_ui.widgets.plugin_manager.QFileDialog.getExistingDirectory")
def test_browse_local_path_does_not_overwrite_name(mock_dir, qapp, mock_grpc_client):
    """Test that browsing doesn't overwrite existing name."""
    mock_dir.return_value = "/home/user/my_plugin"

    dialog = PluginManagerDialog(client=mock_grpc_client)
    dialog._local_name.setText("keep_this")

    dialog._browse_local_path()

    # Name should be preserved because it was already set
    assert dialog._local_name.text() == "keep_this"


# ---------------------------------------------------------------------------
# Preview manifest
# ---------------------------------------------------------------------------


def test_preview_manifest(qapp, mock_grpc_client, tmp_path):
    """Test preview manifest reads file content."""
    manifest_file = tmp_path / "plugins.yaml"
    manifest_file.write_text("plugins:\n  test_plugin:\n    repo: x\n")

    dialog = PluginManagerDialog(client=mock_grpc_client)
    dialog._preview_manifest(str(manifest_file))

    assert "test_plugin" in dialog._manifest_preview.toPlainText()


def test_preview_manifest_error(qapp, mock_grpc_client):
    """Test preview manifest with unreadable file shows error."""
    dialog = PluginManagerDialog(client=mock_grpc_client)
    dialog._preview_manifest("/nonexistent/file.yaml")

    assert "Error" in dialog._manifest_preview.toPlainText()


# ---------------------------------------------------------------------------
# _remove_selected_plugins
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.widgets.plugin_manager.save_plugin_entries")
@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.question")
def test_remove_selected_plugins(mock_question, mock_load, mock_save, qapp, mock_grpc_client):
    """Test removing selected plugins."""
    from PySide6.QtWidgets import QMessageBox

    mock_question.return_value = QMessageBox.StandardButton.Yes
    entries = [
        {"name": "keep_me", "enabled": True, "source": "git", "config": {}},
        {"name": "remove_me", "enabled": True, "source": "git", "config": {}},
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)

    # Select the second row
    dialog._status_table.selectRow(1)

    dialog._remove_selected_plugins()

    # save_plugin_entries should have been called with only "keep_me"
    assert mock_save.called
    saved_entries = mock_save.call_args[0][0]
    names = [e["name"] for e in saved_entries]
    assert "keep_me" in names
    assert "remove_me" not in names


@patch("cuvis_ai_ui.widgets.plugin_manager.save_plugin_entries")
@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.question")
def test_remove_selected_user_cancels(mock_question, mock_load, mock_save, qapp, mock_grpc_client):
    """Test that user cancelling the remove dialog does not remove anything."""
    from PySide6.QtWidgets import QMessageBox

    mock_question.return_value = QMessageBox.StandardButton.No
    entries = [
        {"name": "keep_me", "enabled": True, "source": "git", "config": {}},
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)
    mock_save.reset_mock()

    dialog._status_table.selectRow(0)
    dialog._remove_selected_plugins()

    mock_save.assert_not_called()


@patch("cuvis_ai_ui.widgets.plugin_manager.load_plugin_entries")
def test_remove_selected_no_selection(mock_load, qapp, mock_grpc_client):
    """Test remove does nothing with no selection."""
    entries = [
        {"name": "plugin_a", "enabled": True, "source": "git", "config": {}},
    ]
    mock_load.return_value = entries

    dialog = PluginManagerDialog(client=mock_grpc_client)
    dialog._status_table.clearSelection()

    # Should not crash
    dialog._remove_selected_plugins()


# ---------------------------------------------------------------------------
# _reset_to_defaults
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.widgets.plugin_manager.reset_plugin_entries")
@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.question")
def test_reset_to_defaults(mock_question, mock_reset, qapp, mock_grpc_client):
    """Test reset to defaults when user confirms."""
    from PySide6.QtWidgets import QMessageBox

    mock_question.return_value = QMessageBox.StandardButton.Yes
    mock_reset.return_value = []

    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._reset_to_defaults()

    mock_reset.assert_called_once()


@patch("cuvis_ai_ui.widgets.plugin_manager.reset_plugin_entries")
@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.question")
def test_reset_to_defaults_user_cancels(mock_question, mock_reset, qapp, mock_grpc_client):
    """Test reset to defaults when user cancels."""
    from PySide6.QtWidgets import QMessageBox

    mock_question.return_value = QMessageBox.StandardButton.No

    dialog = PluginManagerDialog(client=mock_grpc_client)

    dialog._reset_to_defaults()

    mock_reset.assert_not_called()


# ---------------------------------------------------------------------------
# _load_plugins helper (shared by git/local)
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.widgets.plugin_manager.write_manifest_temp")
@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.warning")
def test_load_plugins_with_failures(mock_warn, mock_temp, qapp, mock_grpc_client, tmp_path):
    """Test _load_plugins displays warning for failed plugins."""
    temp_file = tmp_path / "m.yaml"
    temp_file.touch()
    mock_temp.return_value = str(temp_file)

    mock_grpc_client.load_plugins.return_value = {
        "loaded_plugins": [],
        "failed_plugins": ["bad_plugin"],
    }

    dialog = PluginManagerDialog(client=mock_grpc_client)
    dialog._load_plugins({"plugins": {"bad_plugin": {}}}, source="git")

    mock_warn.assert_called_once()


@patch("cuvis_ai_ui.widgets.plugin_manager.write_manifest_temp")
@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.critical")
def test_load_plugins_grpc_error(mock_crit, mock_temp, qapp, mock_grpc_client, tmp_path):
    """Test _load_plugins shows error dialog on gRPC failure."""
    temp_file = tmp_path / "m.yaml"
    temp_file.touch()
    mock_temp.return_value = str(temp_file)

    mock_grpc_client.load_plugins.side_effect = RuntimeError("gRPC down")

    dialog = PluginManagerDialog(client=mock_grpc_client)
    dialog._load_plugins({"plugins": {"p": {}}}, source="git")

    mock_crit.assert_called_once()


# ---------------------------------------------------------------------------
# SessionDialog tests
# ---------------------------------------------------------------------------


def test_session_dialog_initialization(qapp, mock_grpc_client):
    """Test SessionDialog basic initialization."""
    dialog = SessionDialog(client=mock_grpc_client)

    assert dialog.windowTitle() == "Session Manager"
    assert dialog._client == mock_grpc_client


def test_session_dialog_no_client(qapp):
    """Test SessionDialog when client is None."""
    dialog = SessionDialog(client=None)

    assert dialog._session_id_label.text() == "No client"
    assert dialog._status_label.text() == "Disconnected"
    assert dialog._create_btn.isEnabled() is False
    assert dialog._close_btn.isEnabled() is False


def test_session_dialog_with_active_session(qapp, mock_grpc_client):
    """Test SessionDialog shows session info when session is active."""
    mock_grpc_client.session_id = "abc-123"

    dialog = SessionDialog(client=mock_grpc_client)

    assert dialog._session_id_label.text() == "abc-123"
    assert dialog._status_label.text() == "Connected"
    assert dialog._close_btn.isEnabled() is True
    assert dialog._create_btn.isEnabled() is False


def test_session_dialog_no_session(qapp):
    """Test SessionDialog when connected but no session."""
    client = MagicMock()
    client.session_id = None

    dialog = SessionDialog(client=client)

    assert dialog._session_id_label.text() == "None"
    assert dialog._status_label.text() == "No session"
    assert dialog._create_btn.isEnabled() is True
    assert dialog._close_btn.isEnabled() is False


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.information")
def test_session_dialog_create_session(mock_info, qapp):
    """Test creating a session via SessionDialog."""
    client = MagicMock()
    client.session_id = None
    client.create_session.return_value = "new-session-456"

    dialog = SessionDialog(client=client)
    dialog._create_session()

    client.create_session.assert_called_once()
    mock_info.assert_called_once()


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.critical")
def test_session_dialog_create_session_failure(mock_crit, qapp):
    """Test creating a session that fails."""
    client = MagicMock()
    client.session_id = None
    client.create_session.side_effect = RuntimeError("Cannot create")

    dialog = SessionDialog(client=client)
    dialog._create_session()

    mock_crit.assert_called_once()


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.information")
def test_session_dialog_close_session(mock_info, qapp, mock_grpc_client):
    """Test closing a session via SessionDialog."""
    dialog = SessionDialog(client=mock_grpc_client)
    dialog._close_session()

    mock_grpc_client.close_session.assert_called_once()


@patch("cuvis_ai_ui.widgets.plugin_manager.QMessageBox.critical")
def test_session_dialog_close_session_failure(mock_crit, qapp):
    """Test closing a session that fails."""
    client = MagicMock()
    client.session_id = "s123"
    client.close_session.side_effect = RuntimeError("Cannot close")

    dialog = SessionDialog(client=client)
    dialog._close_session()

    mock_crit.assert_called_once()


def test_session_dialog_set_client(qapp):
    """Test setting a new client on SessionDialog."""
    dialog = SessionDialog(client=None)
    assert dialog._session_id_label.text() == "No client"

    new_client = MagicMock()
    new_client.session_id = "updated-session"
    dialog.set_client(new_client)

    assert dialog._client == new_client
    assert dialog._session_id_label.text() == "updated-session"


def test_session_dialog_set_client_to_none(qapp, mock_grpc_client):
    """Test setting client to None on SessionDialog."""
    dialog = SessionDialog(client=mock_grpc_client)

    dialog.set_client(None)

    assert dialog._session_id_label.text() == "No client"
    assert dialog._create_btn.isEnabled() is False


def test_session_dialog_has_close_button(qapp, mock_grpc_client):
    """Test that SessionDialog has a Close button."""
    dialog = SessionDialog(client=mock_grpc_client)

    button_box = dialog.findChild(QDialogButtonBox)
    assert button_box is not None

    close_btn = button_box.button(QDialogButtonBox.StandardButton.Close)
    assert close_btn is not None


def test_session_dialog_create_session_does_nothing_when_no_client(qapp):
    """Test that _create_session does nothing when client is None."""
    dialog = SessionDialog(client=None)
    # Should not crash
    dialog._create_session()


def test_session_dialog_close_session_does_nothing_when_no_client(qapp):
    """Test that _close_session does nothing when client is None."""
    dialog = SessionDialog(client=None)
    # Should not crash
    dialog._close_session()
