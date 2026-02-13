"""Plugin manager widget for loading and managing cuvis-ai plugins.

This module provides dialogs and widgets for:
- Loading plugins from Git repositories
- Loading plugins from local paths
- Loading plugins from manifest files (YAML)
- Viewing loaded plugin status
- Managing plugin lifecycle
"""

from pathlib import Path
from typing import Any

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..grpc.client import CuvisAIClient
from ..plugin_settings import (
    load_plugin_entries,
    merge_plugin_entries,
    reset_plugin_entries,
    save_plugin_entries,
    write_manifest_temp,
)

STATUS_COL_LOAD = 0
STATUS_COL_NAME = 1
STATUS_COL_TYPE = 2
STATUS_COL_SOURCE = 3
STATUS_COL_PROVIDES = 4


class PluginManagerDialog(QDialog):
    """Dialog for managing cuvis-ai plugins.

    Provides tabs for:
    - Loaded plugins (status table)
    - Load from Git (URL + ref input)
    - Load from Local (path browser)
    - Load from Manifest (YAML file)

    Signals:
        plugins_loaded: Emitted when plugins are loaded (loaded_names: list)
    """

    plugins_loaded = Signal(list)

    def __init__(
        self,
        client: CuvisAIClient,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the dialog.

        Args:
            client: gRPC client for plugin operations
            parent: Parent widget
        """
        super().__init__(parent)
        self._client = client
        self._plugin_entries: list[dict[str, Any]] = []
        self._is_refreshing = False

        self.setWindowTitle("Plugin Manager")
        self.setMinimumSize(600, 500)
        self.resize(700, 550)

        self._setup_ui()
        self._refresh_status()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Status tab
        status_widget = self._create_status_tab()
        tabs.addTab(status_widget, "Loaded Plugins")

        # Git tab
        git_widget = self._create_git_tab()
        tabs.addTab(git_widget, "Load from Git")

        # Local tab
        local_widget = self._create_local_tab()
        tabs.addTab(local_widget, "Load from Local")

        # Manifest tab
        manifest_widget = self._create_manifest_tab()
        tabs.addTab(manifest_widget, "Load from Manifest")

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)

    def _create_status_tab(self) -> QWidget:
        """Create the loaded plugins status tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Status table
        self._status_table = QTableWidget()
        self._status_table.setColumnCount(5)
        self._status_table.setHorizontalHeaderLabels(
            ["Load", "Plugin Name", "Type", "Source", "Provided Nodes"]
        )
        header = self._status_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(STATUS_COL_LOAD, QHeaderView.ResizeMode.ResizeToContents)
        self._status_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._status_table.itemChanged.connect(self._on_status_item_changed)
        layout.addWidget(self._status_table)

        # Actions
        actions_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Status")
        refresh_btn.clicked.connect(self._refresh_status)
        actions_layout.addWidget(refresh_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected_plugins)
        actions_layout.addWidget(remove_btn)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        actions_layout.addWidget(reset_btn)

        layout.addLayout(actions_layout)

        return widget

    def _create_git_tab(self) -> QWidget:
        """Create the load from Git tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Form
        form_group = QGroupBox("Git Repository")
        form_layout = QFormLayout(form_group)

        self._git_name = QLineEdit()
        self._git_name.setPlaceholderText("plugin_name")
        form_layout.addRow("Plugin Name:", self._git_name)

        self._git_url = QLineEdit()
        self._git_url.setPlaceholderText("git@gitlab.example.com:org/repo.git")
        form_layout.addRow("Repository URL:", self._git_url)

        self._git_ref = QLineEdit()
        self._git_ref.setPlaceholderText("main, v1.0.0, or commit hash")
        self._git_ref.setText("main")
        form_layout.addRow("Ref (branch/tag):", self._git_ref)

        layout.addWidget(form_group)

        # Provided nodes (optional)
        provides_group = QGroupBox("Provided Nodes (optional)")
        provides_layout = QVBoxLayout(provides_group)

        provides_layout.addWidget(
            QLabel("List node class paths, one per line. Leave empty to auto-discover.")
        )

        self._git_provides = QTextEdit()
        self._git_provides.setPlaceholderText(
            "e.g.:\nmy_plugin.node.MyNode\nmy_plugin.node.AnotherNode"
        )
        provides_layout.addWidget(self._git_provides)

        layout.addWidget(provides_group)

        # Load button
        load_btn = QPushButton("Load Plugin")
        load_btn.clicked.connect(self._load_git_plugin)
        layout.addWidget(load_btn)

        layout.addStretch()
        return widget

    def _create_local_tab(self) -> QWidget:
        """Create the load from local path tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Form
        form_group = QGroupBox("Local Path")
        form_layout = QFormLayout(form_group)

        self._local_name = QLineEdit()
        self._local_name.setPlaceholderText("plugin_name")
        form_layout.addRow("Plugin Name:", self._local_name)

        path_layout = QHBoxLayout()
        self._local_path = QLineEdit()
        self._local_path.setPlaceholderText("D:/path/to/plugin")
        path_layout.addWidget(self._local_path)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_local_path)
        path_layout.addWidget(browse_btn)

        form_layout.addRow("Path:", path_layout)

        layout.addWidget(form_group)

        # Provided nodes (optional)
        provides_group = QGroupBox("Provided Nodes (optional)")
        provides_layout = QVBoxLayout(provides_group)

        provides_layout.addWidget(
            QLabel("List node class paths, one per line. Leave empty to auto-discover.")
        )

        self._local_provides = QTextEdit()
        self._local_provides.setPlaceholderText(
            "e.g.:\nmy_plugin.node.MyNode\nmy_plugin.node.AnotherNode"
        )
        provides_layout.addWidget(self._local_provides)

        layout.addWidget(provides_group)

        # Load button
        load_btn = QPushButton("Load Plugin")
        load_btn.clicked.connect(self._load_local_plugin)
        layout.addWidget(load_btn)

        layout.addStretch()
        return widget

    def _create_manifest_tab(self) -> QWidget:
        """Create the load from manifest tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Instructions
        layout.addWidget(
            QLabel(
                "Load plugins from a YAML manifest file.\n"
                "The manifest defines multiple plugins with their sources and nodes."
            )
        )

        # File selection
        file_group = QGroupBox("Manifest File")
        file_layout = QHBoxLayout(file_group)

        self._manifest_path = QLineEdit()
        self._manifest_path.setPlaceholderText("Select manifest YAML file...")
        file_layout.addWidget(self._manifest_path)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_manifest)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        # Preview
        preview_group = QGroupBox("Manifest Preview")
        preview_layout = QVBoxLayout(preview_group)

        self._manifest_preview = QTextEdit()
        self._manifest_preview.setReadOnly(True)
        self._manifest_preview.setPlaceholderText("Manifest contents will appear here...")
        preview_layout.addWidget(self._manifest_preview)

        layout.addWidget(preview_group)

        # Load button
        load_btn = QPushButton("Load Plugins from Manifest")
        load_btn.clicked.connect(self._load_manifest_plugins)
        layout.addWidget(load_btn)

        return widget

    def _refresh_status(self) -> None:
        """Refresh the loaded plugins status table."""
        self._is_refreshing = True
        self._status_table.blockSignals(True)
        self._status_table.setRowCount(0)

        self._plugin_entries = load_plugin_entries()

        loaded_node_counts: dict[str, int] = {}
        try:
            nodes = self._client.list_available_nodes()
            for node in nodes:
                if node.get("source") != "plugin":
                    continue
                plugin_name = node.get("plugin_name") or ""
                if plugin_name:
                    loaded_node_counts[plugin_name] = loaded_node_counts.get(plugin_name, 0) + 1
        except Exception as e:
            logger.error(f"Failed to refresh plugin status: {e}")
            QMessageBox.warning(self, "Warning", f"Failed to refresh plugin status:\n{e}")

        self._status_table.setRowCount(len(self._plugin_entries))
        for row, entry in enumerate(self._plugin_entries):
            load_item = QTableWidgetItem()
            load_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            load_item.setCheckState(
                Qt.CheckState.Checked if entry.get("enabled", True) else Qt.CheckState.Unchecked
            )
            self._status_table.setItem(row, STATUS_COL_LOAD, load_item)

            name_item = QTableWidgetItem(entry.get("name", ""))
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._status_table.setItem(row, STATUS_COL_NAME, name_item)

            type_item = QTableWidgetItem(entry.get("source", "plugin"))
            type_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._status_table.setItem(row, STATUS_COL_TYPE, type_item)

            config = entry.get("config", {})
            source_text = entry.get("origin") or ""
            if not source_text:
                if isinstance(config, dict):
                    if "repo" in config:
                        source_text = str(config.get("repo", ""))
                    elif "path" in config:
                        source_text = str(config.get("path", ""))
            source_item = QTableWidgetItem(source_text)
            source_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._status_table.setItem(row, STATUS_COL_SOURCE, source_item)

            provides = config.get("provides") if isinstance(config, dict) else None
            if isinstance(provides, list) and provides:
                provided_text = str(len(provides))
            elif entry.get("name") in loaded_node_counts:
                provided_text = str(loaded_node_counts.get(entry.get("name"), 0))
            else:
                provided_text = "auto"
            provided_item = QTableWidgetItem(provided_text)
            provided_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._status_table.setItem(row, STATUS_COL_PROVIDES, provided_item)

        self._status_table.blockSignals(False)
        self._is_refreshing = False

    def _on_status_item_changed(self, item: QTableWidgetItem) -> None:
        """Handle load checkbox toggles."""
        if self._is_refreshing:
            return
        if item.column() != STATUS_COL_LOAD:
            return

        name_item = self._status_table.item(item.row(), STATUS_COL_NAME)
        if name_item is None:
            return
        name = name_item.text()
        enabled = item.checkState() == Qt.CheckState.Checked

        updated = False
        for entry in self._plugin_entries:
            if entry.get("name") == name:
                entry["enabled"] = enabled
                updated = True
                break

        if updated:
            save_plugin_entries(self._plugin_entries)

    def _remove_selected_plugins(self) -> None:
        """Remove selected plugins from persistence."""
        rows = {item.row() for item in self._status_table.selectedItems()}
        if not rows:
            return

        names = []
        for row in sorted(rows):
            name_item = self._status_table.item(row, STATUS_COL_NAME)
            if name_item is not None:
                names.append(name_item.text())

        if not names:
            return

        reply = QMessageBox.question(
            self,
            "Remove Plugins",
            "Remove selected plugins from the persistent list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._plugin_entries = [
            entry for entry in self._plugin_entries if entry.get("name") not in names
        ]
        save_plugin_entries(self._plugin_entries)
        self._refresh_status()

    def _reset_to_defaults(self) -> None:
        """Reset persisted plugins to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset Plugins",
            "Reset plugins to defaults? This will clear your saved list.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._plugin_entries = reset_plugin_entries()
        self._refresh_status()

    def _persist_plugins_from_manifest(
        self,
        manifest: dict[str, Any],
        loaded: list[str],
        source: str,
        origin: str | None = None,
    ) -> None:
        if not loaded:
            return

        plugins = manifest.get("plugins", {})
        if not isinstance(plugins, dict):
            return

        loaded_set = set(loaded)
        new_entries: list[dict[str, Any]] = []
        for name, config in plugins.items():
            if not isinstance(name, str) or not isinstance(config, dict):
                continue
            if name not in loaded_set:
                continue
            entry = {
                "name": name,
                "enabled": True,
                "source": source,
                "config": config,
            }
            if origin:
                entry["origin"] = origin
            new_entries.append(entry)

        if not new_entries:
            return

        self._plugin_entries = merge_plugin_entries(self._plugin_entries, new_entries)
        save_plugin_entries(self._plugin_entries)

    def _format_failed_plugins(self, failed: Any) -> str:
        if isinstance(failed, dict):
            return "\n".join(f"  {k}: {v}" for k, v in failed.items())
        if isinstance(failed, list):
            return "\n".join(f"  {name}" for name in failed)
        return str(failed)

    def _browse_local_path(self) -> None:
        """Browse for local plugin path."""
        path = QFileDialog.getExistingDirectory(self, "Select Plugin Directory")
        if path:
            self._local_path.setText(path)
            # Auto-fill name from directory name
            if not self._local_name.text():
                self._local_name.setText(Path(path).name)

    def _browse_manifest(self) -> None:
        """Browse for manifest file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Manifest File", "", "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        if path:
            self._manifest_path.setText(path)
            self._preview_manifest(path)

    def _preview_manifest(self, path: str) -> None:
        """Preview manifest file contents."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self._manifest_preview.setPlainText(content)
        except Exception as e:
            self._manifest_preview.setPlainText(f"Error reading file: {e}")

    def _load_git_plugin(self) -> None:
        """Load a plugin from Git."""
        name = self._git_name.text().strip()
        url = self._git_url.text().strip()
        ref = self._git_ref.text().strip() or "main"
        provides_text = self._git_provides.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "Error", "Please enter a plugin name.")
            return

        if not url:
            QMessageBox.warning(self, "Error", "Please enter a repository URL.")
            return

        # Build manifest
        manifest: dict[str, Any] = {
            "plugins": {
                name: {
                    "repo": url,
                    "ref": ref,
                }
            }
        }

        # Add provides if specified
        if provides_text:
            provides = [line.strip() for line in provides_text.split("\n") if line.strip()]
            manifest["plugins"][name]["provides"] = provides

        self._load_plugins(manifest, source="git")

    def _load_local_plugin(self) -> None:
        """Load a plugin from local path."""
        name = self._local_name.text().strip()
        path = self._local_path.text().strip()
        provides_text = self._local_provides.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "Error", "Please enter a plugin name.")
            return

        if not path:
            QMessageBox.warning(self, "Error", "Please enter a path.")
            return

        if not Path(path).exists():
            QMessageBox.warning(self, "Error", f"Path does not exist: {path}")
            return

        # Build manifest
        manifest: dict[str, Any] = {
            "plugins": {
                name: {
                    "path": path,
                }
            }
        }

        # Add provides if specified
        if provides_text:
            provides = [line.strip() for line in provides_text.split("\n") if line.strip()]
            manifest["plugins"][name]["provides"] = provides

        self._load_plugins(manifest, source="local")

    def _load_manifest_plugins(self) -> None:
        """Load plugins from manifest file."""
        path = self._manifest_path.text().strip()

        if not path:
            QMessageBox.warning(self, "Error", "Please select a manifest file.")
            return

        if not Path(path).exists():
            QMessageBox.warning(self, "Error", f"File does not exist: {path}")
            return

        try:
            import yaml

            with open(path, "r", encoding="utf-8") as f:
                manifest = yaml.safe_load(f) or {}
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read manifest:\n{e}")
            return

        if not isinstance(manifest, dict) or "plugins" not in manifest:
            QMessageBox.critical(self, "Error", "Manifest is missing a 'plugins' section.")
            return

        try:
            result = self._client.load_plugins(path)

            loaded = result.get("loaded_plugins", [])
            failed = result.get("failed_plugins", [])

            if loaded:
                QMessageBox.information(self, "Success", f"Loaded plugins: {', '.join(loaded)}")
                self.plugins_loaded.emit(loaded)
                self._persist_plugins_from_manifest(
                    manifest,
                    loaded,
                    source="manifest",
                    origin=path,
                )
                self._refresh_status()

            if failed:
                errors = self._format_failed_plugins(failed)
                QMessageBox.warning(
                    self, "Partial Failure", f"Some plugins failed to load:\n{errors}"
                )

        except Exception as e:
            logger.error(f"Failed to load plugins: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load plugins:\n{e}")

    def _load_plugins(
        self,
        manifest: dict[str, Any],
        source: str | None = None,
        origin: str | None = None,
    ) -> None:
        """Load plugins from a manifest dictionary.

        Args:
            manifest: Plugin manifest dictionary
            source: Plugin source label for persistence (git/local/manifest)
            origin: Optional source path for display
        """
        temp_path = write_manifest_temp(manifest)

        try:
            result = self._client.load_plugins(temp_path)

            loaded = result.get("loaded_plugins", [])
            failed = result.get("failed_plugins", [])

            if loaded:
                QMessageBox.information(self, "Success", f"Loaded plugins: {', '.join(loaded)}")
                self.plugins_loaded.emit(loaded)
                if source:
                    self._persist_plugins_from_manifest(
                        manifest,
                        loaded,
                        source=source,
                        origin=origin,
                    )
                self._refresh_status()

            if failed:
                errors = self._format_failed_plugins(failed)
                QMessageBox.warning(
                    self, "Partial Failure", f"Some plugins failed to load:\n{errors}"
                )

        except Exception as e:
            logger.error(f"Failed to load plugins: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load plugins:\n{e}")
        finally:
            try:
                Path(temp_path).unlink()
            except Exception:
                pass


class SessionDialog(QDialog):
    """Dialog for managing gRPC sessions.

    Provides:
    - Current session info
    - Create new session
    - Close session
    """

    session_changed = Signal(str)  # session_id

    def __init__(
        self,
        client: CuvisAIClient | None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the dialog.

        Args:
            client: gRPC client (may be None)
            parent: Parent widget
        """
        super().__init__(parent)
        self._client = client

        self.setWindowTitle("Session Manager")
        self.setMinimumSize(400, 200)

        self._setup_ui()
        self._update_display()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Session info
        info_group = QGroupBox("Current Session")
        info_layout = QFormLayout(info_group)

        self._session_id_label = QLabel("Not connected")
        info_layout.addRow("Session ID:", self._session_id_label)

        self._status_label = QLabel("Disconnected")
        info_layout.addRow("Status:", self._status_label)

        layout.addWidget(info_group)

        # Actions
        actions_layout = QHBoxLayout()

        self._create_btn = QPushButton("Create Session")
        self._create_btn.clicked.connect(self._create_session)
        actions_layout.addWidget(self._create_btn)

        self._close_btn = QPushButton("Close Session")
        self._close_btn.clicked.connect(self._close_session)
        actions_layout.addWidget(self._close_btn)

        layout.addLayout(actions_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)

    def _update_display(self) -> None:
        """Update the display with current session info."""
        if self._client is None:
            self._session_id_label.setText("No client")
            self._status_label.setText("Disconnected")
            self._create_btn.setEnabled(False)
            self._close_btn.setEnabled(False)
            return

        session_id = self._client.session_id
        if session_id:
            self._session_id_label.setText(session_id)
            self._status_label.setText("Connected")
            self._create_btn.setEnabled(False)
            self._close_btn.setEnabled(True)
        else:
            self._session_id_label.setText("None")
            self._status_label.setText("No session")
            self._create_btn.setEnabled(True)
            self._close_btn.setEnabled(False)

    def _create_session(self) -> None:
        """Create a new session."""
        if self._client is None:
            return

        try:
            session_id = self._client.create_session()
            self._update_display()
            self.session_changed.emit(session_id)
            QMessageBox.information(self, "Success", f"Created session: {session_id}")
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create session:\n{e}")

    def _close_session(self) -> None:
        """Close the current session."""
        if self._client is None:
            return

        try:
            self._client.close_session()
            self._update_display()
            self.session_changed.emit("")
            QMessageBox.information(self, "Success", "Session closed")
        except Exception as e:
            logger.error(f"Failed to close session: {e}")
            QMessageBox.critical(self, "Error", f"Failed to close session:\n{e}")

    def set_client(self, client: CuvisAIClient | None) -> None:
        """Set the gRPC client.

        Args:
            client: gRPC client or None
        """
        self._client = client
        self._update_display()
