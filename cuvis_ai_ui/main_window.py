"""Main window for the cuvis-ai visualization application.

This module provides the Qt MainWindow with:
- NodeGraphQt canvas for visual pipeline editing
- Menu bar with File, Edit, View, Tools menus
- Toolbar with common actions
- Status bar with connection indicator
- Dock widgets for the pipelines of a folder, node palette and property editor
"""

import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from loguru import logger
from NodeGraphQt import NodeGraph
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QWidget,
)

from .adapters import NodeRegistry, PipelineSerializer
from .grpc.client import CuvisAIClient, check_cancelled
from .server import ServerManager, is_listening
from .widgets.blocking_task import (
    SERVER_WAIT_CANCELLED,
    TaskStatus,
    run_blocking,
    wait_for_server,
)
from .widgets.canvas_drop_target import CanvasDropTarget
from .widgets.connection_dialog import ConnectionDialog
from .widgets.pipeline_browser import PipelineBrowser
from .widgets.pipeline_info_dialog import PipelineInfoDialog
from .workspace import list_pipelines


class _ViewerModifierSync(QObject):
    """Keep NodeGraphQt viewer modifier state in sync with mouse events."""

    def __init__(self, viewer: Any) -> None:
        super().__init__(viewer)
        self._viewer = viewer

    def eventFilter(self, obj: Any, event: Any) -> bool:  # type: ignore[override]
        if obj is self._viewer:
            if event.type() in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseMove,
                QEvent.Type.Wheel,
            ):
                mods = event.modifiers()
                self._viewer.ALT_state = bool(mods & Qt.KeyboardModifier.AltModifier)
                self._viewer.CTRL_state = bool(mods & Qt.KeyboardModifier.ControlModifier)
                self._viewer.SHIFT_state = bool(mods & Qt.KeyboardModifier.ShiftModifier)
            elif event.type() == QEvent.Type.FocusOut:
                self._viewer.clear_key_state()
        return False


class MainWindow(QMainWindow):
    """Main application window for cuvis-ai visualizer.

    Provides the visual pipeline editor with:
    - Central NodeGraphQt canvas
    - Left dock: Pipelines of the open folder, above the node palette (drag-and-drop)
    - Right dock: Property editor
    - Top: Menu bar and toolbar
    - Bottom: Status bar

    Signals:
        pipeline_loaded: Emitted when a pipeline is loaded (path: str)
        pipeline_saved: Emitted when a pipeline is saved (path: str)
        node_selected: Emitted when a node is selected (node or None)
        connection_status_changed: Emitted when gRPC connection status changes (connected: bool)
        folder_changed: Emitted when a pipelines folder is opened, before its first
            pipeline loads (folder: Path)
    """

    pipeline_loaded = Signal(str)
    pipeline_saved = Signal(str)
    node_selected = Signal(object)
    connection_status_changed = Signal(bool)
    folder_changed = Signal(object)

    def __init__(
        self,
        client: CuvisAIClient | None = None,
        parent: Any = None,
    ) -> None:
        """Initialize the main window.

        Args:
            client: Optional gRPC client (will create one if not provided)
            parent: Parent widget
        """
        super().__init__(parent)

        # gRPC client
        self._client = client
        self._session_id: str | None = None
        self._server_manager: ServerManager | None = None

        # Node registry for available nodes
        self._node_registry = NodeRegistry()

        # Current file path and pipelines folder
        self._current_file: Path | None = None
        self._current_folder: Path | None = None
        self._unsaved_changes = False

        # Pipeline metadata
        self._metadata: dict[str, Any] = {}

        # Setup UI
        self._setup_window()
        self._setup_graph()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_status_bar()
        self._setup_dock_widgets()
        self._setup_connections()

    def _setup_window(self) -> None:
        """Configure the main window."""
        self.setWindowTitle("Cuvis.AI UI")
        self.setMinimumSize(1200, 800)
        self.resize(1600, 1000)

    def _setup_graph(self) -> None:
        """Setup the NodeGraphQt canvas."""
        self._graph = NodeGraph()
        self._graph.set_background_color(40, 40, 40)
        self._graph.set_grid_mode(1)  # Grid with dots

        # Get the graph widget and set as central widget
        graph_widget = self._graph.widget
        self.setCentralWidget(graph_widget)

        # Create serializer
        self._serializer = PipelineSerializer(self._node_registry)

        # Keep viewer modifier state in sync (prevents stuck ALT panning)
        viewer = self._graph.viewer()
        viewer.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._viewer_modifier_sync = _ViewerModifierSync(viewer)
        viewer.installEventFilter(self._viewer_modifier_sync)

        # Accept drops from the node palette
        self._canvas_drop_target = CanvasDropTarget(viewer, self._graph, self._node_registry)
        self._canvas_drop_target.install()

    def _setup_menus(self) -> None:
        """Setup the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_pipeline)
        file_menu.addAction(new_action)

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_pipeline)
        file_menu.addAction(open_action)

        open_folder_action = QAction("Open &Folder...", self)
        open_folder_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)

        file_menu.addSeparator()

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_pipeline)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self.save_pipeline_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        info_action = QAction("Pipeline &Info...", self)
        info_action.setShortcut(QKeySequence("Ctrl+I"))
        info_action.triggered.connect(self._show_pipeline_info)
        file_menu.addAction(info_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        undo_action = QAction("&Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self._undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("&Redo", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self._redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        delete_action = QAction("&Delete", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self._delete_selected)
        edit_menu.addAction(delete_action)

        select_all_action = QAction("Select &All", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self._select_all)
        edit_menu.addAction(select_all_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        fit_action = QAction("&Fit to View", self)
        fit_action.setShortcut(QKeySequence("F"))
        fit_action.triggered.connect(self._fit_to_view)
        view_menu.addAction(fit_action)

        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        zoom_in_action.triggered.connect(self._zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        zoom_out_action.triggered.connect(self._zoom_out)
        view_menu.addAction(zoom_out_action)

        view_menu.addSeparator()

        self._pipelines_action = QAction("P&ipelines", self)
        self._pipelines_action.setCheckable(True)
        self._pipelines_action.setChecked(False)
        view_menu.addAction(self._pipelines_action)

        self._palette_action = QAction("&Node Palette", self)
        self._palette_action.setCheckable(True)
        self._palette_action.setChecked(True)
        view_menu.addAction(self._palette_action)

        self._properties_action = QAction("&Properties", self)
        self._properties_action.setCheckable(True)
        self._properties_action.setChecked(True)
        view_menu.addAction(self._properties_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        connect_action = QAction("&Connect to Server...", self)
        connect_action.triggered.connect(self._show_connection_dialog)
        tools_menu.addAction(connect_action)

        refresh_nodes_action = QAction("&Refresh Node List", self)
        refresh_nodes_action.triggered.connect(self._refresh_nodes)
        tools_menu.addAction(refresh_nodes_action)
        self._refresh_nodes_action = refresh_nodes_action

        tools_menu.addSeparator()

        plugins_action = QAction("&Manage Plugins...", self)
        plugins_action.triggered.connect(self._show_plugin_manager)
        tools_menu.addAction(plugins_action)
        self._plugins_action = plugins_action

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self) -> None:
        """Setup the main toolbar."""
        self._toolbar = QToolBar("Main Toolbar")
        self._toolbar.setMovable(False)

        # File actions
        self._toolbar.addAction("New").triggered.connect(self.new_pipeline)
        self._toolbar.addAction("Open").triggered.connect(self.open_pipeline)
        self._toolbar.addAction("Save").triggered.connect(self.save_pipeline)

        self._toolbar.addSeparator()

        # Edit actions
        self._toolbar.addAction("Undo").triggered.connect(self._undo)
        self._toolbar.addAction("Redo").triggered.connect(self._redo)
        self._toolbar.addAction("Delete").triggered.connect(self._delete_selected)

        self._toolbar.addSeparator()

        # View actions
        self._toolbar.addAction("Fit").triggered.connect(self._fit_to_view)

        self._combine_menu_and_toolbar()

    def _combine_menu_and_toolbar(self) -> None:
        """Place the menu bar and toolbar on a single line."""
        menu_bar = self.menuBar()
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)

        menu_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._toolbar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        layout.addWidget(menu_bar, 1)
        layout.addWidget(self._toolbar, 0)
        container.setLayout(layout)
        self.setMenuWidget(container)

    def _setup_status_bar(self) -> None:
        """Setup the status bar."""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        # Connection status indicator
        self._connection_label = QLabel("Not connected")
        self._status_bar.addPermanentWidget(self._connection_label)
        if self._client is not None:
            self._session_id = self._client.session_id
        self._update_connection_status(self._client is not None)

    def _setup_dock_widgets(self) -> None:
        """Setup dock widgets for palette and properties."""
        # Node palette dock (left side)
        self._palette_dock = QDockWidget("Node Palette", self)
        self._palette_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._palette_dock)
        self._palette_action.toggled.connect(self._palette_dock.setVisible)
        self._palette_dock.visibilityChanged.connect(self._palette_action.setChecked)

        # Pipelines dock (left side, above the palette), shown once a folder is open
        self._pipeline_browser = PipelineBrowser(self)
        self._pipeline_browser.pipeline_selected.connect(self._on_pipeline_selected)
        self._pipelines_dock = QDockWidget("Pipelines", self)
        self._pipelines_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._pipelines_dock.setWidget(self._pipeline_browser)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._pipelines_dock)
        self.splitDockWidget(self._pipelines_dock, self._palette_dock, Qt.Orientation.Vertical)
        self._pipelines_dock.setVisible(False)
        self._pipelines_action.toggled.connect(self._pipelines_dock.setVisible)
        self._pipelines_dock.visibilityChanged.connect(self._pipelines_action.setChecked)

        # Properties dock (right side)
        self._properties_dock = QDockWidget("Properties", self)
        self._properties_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._properties_dock)
        self._properties_action.toggled.connect(self._properties_dock.setVisible)
        self._properties_dock.visibilityChanged.connect(self._properties_action.setChecked)

    def _setup_connections(self) -> None:
        """Setup signal/slot connections."""
        # Graph signals
        self._graph.node_selected.connect(self._on_node_selected)
        self._graph.nodes_deleted.connect(self._on_nodes_deleted)
        # Every graph edit (add, move, connect, delete) goes through the undo stack
        self._graph.undo_stack().indexChanged.connect(self._on_graph_edited)

    def set_palette_widget(self, widget: Any) -> None:
        """Set the node palette widget.

        Args:
            widget: Widget to use as node palette
        """
        self._palette_dock.setWidget(widget)

    def set_properties_widget(self, widget: Any) -> None:
        """Set the properties editor widget.

        Args:
            widget: Widget to use as properties editor
        """
        self._properties_dock.setWidget(widget)
        property_changed = getattr(widget, "property_changed", None)
        if property_changed is not None:
            property_changed.connect(self._on_property_changed)

    @property
    def graph(self) -> NodeGraph:
        """Get the NodeGraphQt graph instance."""
        return self._graph

    @property
    def node_registry(self) -> NodeRegistry:
        """Get the node registry."""
        return self._node_registry

    @property
    def client(self) -> CuvisAIClient | None:
        """Get the gRPC client."""
        return self._client

    @property
    def plugins_action(self) -> QAction | None:
        """Get the Plugins menu action (if available)."""
        return getattr(self, "_plugins_action", None)

    @property
    def refresh_nodes_action(self) -> QAction:
        """Get the Tools > Refresh Node List action."""
        return self._refresh_nodes_action

    @property
    def pipeline_browser(self) -> PipelineBrowser:
        """Get the pipelines browser shown in the Pipelines dock."""
        return self._pipeline_browser

    @property
    def current_folder(self) -> Path | None:
        """The open pipelines folder, or None."""
        return self._current_folder

    @property
    def current_file(self) -> Path | None:
        """The open pipeline file, or None."""
        return self._current_file

    def set_known_plugins(self, names: Iterable[str] | None) -> None:
        """Plugin names the server accepted; a pipeline naming another one warns on load.

        None turns the check off (no server).
        """
        self._serializer.known_plugins = set(names) if names is not None else None

    @property
    def session_id(self) -> str | None:
        """Get the current session ID."""
        return self._session_id

    def set_client(self, client: CuvisAIClient) -> None:
        """Set the gRPC client.

        Args:
            client: The gRPC client to use
        """
        self._client = client
        self._session_id = client.session_id
        self._update_connection_status(True)

    @property
    def server_manager(self) -> ServerManager | None:
        """Get the local server manager (if any)."""
        return self._server_manager

    def set_server_manager(self, manager: ServerManager | None) -> None:
        """Set the server manager for local server lifecycle."""
        self._server_manager = manager

    # File operations

    def _confirm_discard(self) -> bool:
        """Ask what to do with unsaved changes; True when the graph may be replaced."""
        if not self._unsaved_changes:
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "The pipeline has unsaved changes. Save them first?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self.save_pipeline()
            return not self._unsaved_changes
        return reply == QMessageBox.StandardButton.Discard

    def new_pipeline(self) -> None:
        """Create a new empty pipeline."""
        if not self._confirm_discard():
            return

        self.node_selected.emit(None)
        self._graph.clear_session()
        self._current_file = None
        self._metadata = {}
        self._unsaved_changes = False
        self._update_title()
        self._pipeline_browser.select(None)
        self._status_bar.showMessage("New pipeline created", 3000)

    def open_pipeline(
        self,
        path: str | Path | None = None,
        *,
        confirm: bool = True,
        warn_dialog: bool = True,
    ) -> bool:
        """Open a pipeline from a YAML file.

        Args:
            path: Optional path to open. If None, shows file dialog.
            confirm: Ask about unsaved changes first.
            warn_dialog: Show load warnings in a dialog; otherwise on the status bar.

        Returns:
            True when the pipeline was opened.
        """
        # Handle Qt signal arguments (triggered signal can pass bool)
        if path is None or isinstance(path, bool):
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Pipeline",
                str(self._current_folder or ""),
                "YAML Files (*.yaml *.yml);;All Files (*)",
            )

        # Validate path (handles cancel dialog, empty string, etc.)
        if not path:
            return False
        if confirm and not self._confirm_discard():
            return False

        path = str(path)
        self.node_selected.emit(None)
        try:
            self._metadata = self._serializer.from_yaml_file(path, self._graph)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open pipeline:\n{e}")
            logger.error(f"Failed to open pipeline {path}: {e}")
            return False

        self._current_file = Path(path)
        self._unsaved_changes = False
        self._update_title()
        self._pipeline_browser.select(self._current_file)
        for node in self._graph.all_nodes():
            node.set_property("selected", False, push_undo=False)
        QTimer.singleShot(0, self._fit_to_view)
        self.pipeline_loaded.emit(path)
        self._status_bar.showMessage(f"Opened: {path}", 3000)
        logger.info(f"Opened pipeline: {path}")
        warnings = self._serializer.last_load_warnings
        if warnings:
            for warning in warnings:
                logger.warning(f"{self._current_file.name}: {warning}")
            if warn_dialog:
                QMessageBox.warning(
                    self,
                    "Pipeline Load Warnings",
                    "The pipeline loaded with warnings:\n\n- "
                    + "\n- ".join(warnings)
                    + "\n\nTip: missing nodes or plugins mean their manifests are not "
                    "loaded. Put the manifests in the pipeline folder's plugins/ "
                    "subfolder, start the UI with --plugins-dir, or use Tools > "
                    "Manage Plugins.",
                )
            else:
                self._status_bar.showMessage(
                    f"Opened {self._current_file.name} with {len(warnings)} warning(s): "
                    + warnings[0]
                )
        return True

    def open_folder(
        self, path: str | Path | None = None, pipeline: str | Path | None = None
    ) -> bool:
        """Open a folder of pipelines in the Pipelines dock.

        ``folder_changed`` is emitted first, so the folder's plugins are
        registered before ``pipeline`` (default: the first one in the folder)
        opens.

        Returns:
            True when the folder was opened.
        """
        if path is None or isinstance(path, bool):
            path = QFileDialog.getExistingDirectory(
                self, "Open Pipelines Folder", str(self._current_folder or "")
            )
        if not path:
            return False

        # Absolute() (not resolve()) so a folder the CLI opened by a relative
        # path (cuvis-ui pipelines) still compares equal to the absolute paths
        # Save As returns. resolve() would also expand Windows 8.3 short
        # names, which breaks comparisons against some tmp paths.
        folder = Path(path).absolute()
        pipelines = list_pipelines(folder)
        if pipeline is not None:
            target: Path | None = Path(pipeline).absolute()
        else:
            target = pipelines[0] if pipelines else None
        if target is not None and not self._confirm_discard():
            return False

        self._current_folder = folder
        self._pipeline_browser.set_folder(folder)
        self._pipelines_dock.setVisible(True)
        self.folder_changed.emit(folder)
        if target is not None:
            self.open_pipeline(target, confirm=False)
        else:
            self._status_bar.showMessage(f"No pipelines in {folder}", 5000)
        return True

    def _on_pipeline_selected(self, path: str) -> None:
        """Open the pipeline picked in the browser, or snap back if the user cancels."""
        if Path(path) == self._current_file:
            return
        if not self.open_pipeline(path, warn_dialog=False):
            self._pipeline_browser.select(self._current_file)

    def save_pipeline(self) -> None:
        """Save the current pipeline."""
        if self._current_file is None:
            self.save_pipeline_as()
            return

        self._save_to_file(self._current_file)

    def save_pipeline_as(self) -> None:
        """Save the pipeline to a new file."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Pipeline As",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)",
        )
        if not path:
            return

        # Ensure .yaml extension
        if not path.endswith((".yaml", ".yml")):
            path += ".yaml"

        self._save_to_file(Path(path))

    def _save_to_file(self, path: Path) -> None:
        """Save the pipeline to a specific file.

        Args:
            path: File path to save to
        """
        try:
            self._serializer.to_yaml_file(self._graph, path, self._metadata)
            self._current_file = path
            self._unsaved_changes = False
            self._update_title()
            if self._current_folder is not None and path.parent == self._current_folder:
                self._pipeline_browser.set_folder(self._current_folder)
            self._pipeline_browser.select(path)
            self.pipeline_saved.emit(str(path))
            self._status_bar.showMessage(f"Saved: {path}", 3000)
            logger.info(f"Saved pipeline: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save pipeline:\n{e}")
            logger.error(f"Failed to save pipeline {path}: {e}")

    # Edit operations

    def _delete_selected(self) -> None:
        """Delete selected nodes; the undo stack's signal marks the pipeline unsaved."""
        selected = self._graph.selected_nodes()
        if selected:
            self._graph.delete_nodes(selected)

    def _select_all(self) -> None:
        """Select all nodes."""
        for node in self._graph.all_nodes():
            node.set_property("selected", True, push_undo=False)

    def _undo(self) -> None:
        """Undo last action; moving the undo stack marks the pipeline unsaved."""
        undo_stack = self._graph.undo_stack()
        if undo_stack and undo_stack.canUndo():
            undo_stack.undo()

    def _redo(self) -> None:
        """Redo last undone action; moving the undo stack marks the pipeline unsaved."""
        undo_stack = self._graph.undo_stack()
        if undo_stack and undo_stack.canRedo():
            undo_stack.redo()

    # View operations

    def _fit_to_view(self) -> None:
        """Fit all nodes into the view."""
        self._graph.fit_to_selection()

    def _zoom_in(self) -> None:
        """Zoom in."""
        zoom = self._graph.get_zoom()
        self._graph.set_zoom(zoom + 0.1)

    def _zoom_out(self) -> None:
        """Zoom out."""
        zoom = self._graph.get_zoom()
        self._graph.set_zoom(zoom - 0.1)

    # Tools operations

    def _show_connection_dialog(self) -> None:
        """Show the server connection dialog."""
        dialog = ConnectionDialog(self)
        if not dialog.exec():
            return

        settings = dialog.get_settings()
        host = settings.get("host", "localhost")
        port = settings.get("port", 50051)

        # Stop a server this window started before giving it up: switching to
        # remote, switching to a different local port nothing listens on yet,
        # or reconnecting to a manager that is no longer answering. Otherwise
        # that process keeps running, unreachable, until the app exits.
        stopped_own_server = False
        if self._server_manager is not None and (
            settings["mode"] == "remote"
            or self._server_manager.port != port
            or not self._server_manager.is_running()
        ):
            self._server_manager.stop()
            self._server_manager = None
            stopped_own_server = True

        # Local mode means this machine. Start a server unless one already listens
        # (started outside the UI, or by an earlier run). A manager still here is
        # this window's own server on this port, alive but not listening yet (a
        # slow first start): wait for it again instead of starting a second one.
        if settings["mode"] == "local":
            host = "localhost"
            if not is_listening(host, port):
                if self._server_manager is None:
                    self._server_manager = ServerManager(port=port)
                    self._server_manager.start()
                waited = wait_for_server(self._server_manager, self)
                if waited.status is TaskStatus.CANCELLED:
                    if not stopped_own_server:
                        # Cancel changes nothing: the old connection, if any, stays
                        self._status_bar.showMessage(SERVER_WAIT_CANCELLED)
                        return
                    # The old client's server was stopped above; drop the client
                    # without a CloseSession call to a server that is gone.
                    self._client = None
                    self._update_connection_status(False)
                    self._status_bar.showMessage(
                        f"{SERVER_WAIT_CANCELLED} The previous local server was "
                        "stopped, so the window is not connected."
                    )
                    return
                if not waited.value:
                    detail = (
                        waited.error
                        or self._server_manager.last_error
                        or "The local gRPC server did not become ready in time."
                    )
                    QMessageBox.warning(self, "Server Start Warning", detail)

        # Close the old client and connect the new one off the UI thread: closing
        # sends CloseSession, which can take its full timeout on a stalled server.
        old_client = self._client
        new_client = CuvisAIClient(host=host, port=port)
        old_closed = False

        def reconnect(stop: threading.Event) -> None:
            nonlocal old_closed
            check_cancelled(stop)
            if old_client is not None:
                try:
                    old_client.disconnect()
                except Exception:
                    pass
            old_closed = True
            check_cancelled(stop)
            new_client.connect(stop=stop)

        connected = run_blocking(
            self, "Connecting", f"Connecting to the server at {host}:{port}...", reconnect
        )
        if connected.status is TaskStatus.DONE:
            self._client = new_client
            self._session_id = new_client.session_id
            self._update_connection_status(True)
            self._status_bar.showMessage(f"Connected to {host}:{port}", 3000)
            logger.info(f"Reconnected to {host}:{port}, session: {self._session_id}")
            return
        if connected.status is TaskStatus.CANCELLED and not old_closed:
            self._status_bar.showMessage("Connecting cancelled; the old connection stays.")
            return
        self._client = None
        self._update_connection_status(False)
        if connected.status is TaskStatus.CANCELLED:
            self._status_bar.showMessage("Connecting cancelled; not connected.")
        else:
            QMessageBox.warning(
                self,
                "Connection Failed",
                f"Failed to connect to {host}:{port}:\n{connected.error}",
            )

    def _refresh_nodes(self) -> None:
        """Refresh the node list from the server."""
        if self._client is None:
            QMessageBox.warning(self, "Not Connected", "Please connect to a server first.")
            return

        try:
            nodes = self._client.list_available_nodes()
            self._node_registry.clear()
            self._node_registry.register_nodes(nodes)
            self._status_bar.showMessage(f"Refreshed: {len(nodes)} nodes available", 3000)
            logger.info(f"Refreshed node list: {len(nodes)} nodes")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh nodes:\n{e}")
            logger.error(f"Failed to refresh nodes: {e}")

    def _show_pipeline_info(self) -> None:
        """Show the pipeline information dialog."""
        dialog = PipelineInfoDialog(self._metadata, self)
        if dialog.exec():
            # User clicked OK - update metadata
            self._metadata = dialog.get_metadata()
            self._unsaved_changes = True
            self._update_title()
            self._status_bar.showMessage("Pipeline information updated", 3000)
            logger.info("Pipeline metadata updated")

    def _show_plugin_manager(self) -> None:
        """Show the plugin manager dialog."""
        # This will be implemented by the plugin manager widget
        self._status_bar.showMessage("Plugin manager not yet implemented", 3000)

    def _show_about(self) -> None:
        """Show the about dialog."""
        QMessageBox.about(
            self,
            "About Cuvis.AI UI",
            "Cuvis.AI UI\n\n"
            "A visual editor for creating and editing\n"
            "cuvis-ai ML pipelines.\n\n"
            "Built with NodeGraphQt and PySide6.",
        )

    # Event handlers

    def _on_node_selected(self, node: Any) -> None:
        """Handle node selection."""
        self.node_selected.emit(node)

    def _on_nodes_deleted(self, node_ids: list[str]) -> None:
        """Handle node deletion."""
        self._unsaved_changes = True
        self._update_title()

    def _on_graph_edited(self, _index: int) -> None:
        """Mark the pipeline dirty when the graph's undo stack moves."""
        if not self._unsaved_changes:
            self._unsaved_changes = True
            self._update_title()

    def _on_property_changed(self, _key: str, _value: Any) -> None:
        """Mark the pipeline dirty when the properties editor changes a value."""
        if not self._unsaved_changes:
            self._unsaved_changes = True
            self._update_title()

    def _update_title(self) -> None:
        """Update the window title."""
        title = "Cuvis.AI UI"
        if self._current_file:
            title = f"{self._current_file.name} - {title}"
        if self._unsaved_changes:
            title = f"* {title}"
        self.setWindowTitle(title)

    def _update_connection_status(self, connected: bool) -> None:
        """Update the connection status indicator.

        Args:
            connected: Whether we're connected to the server
        """
        if connected:
            self._connection_label.setText("Connected")
            self._connection_label.setStyleSheet("color: green;")
        else:
            self._connection_label.setText("Not connected")
            self._connection_label.setStyleSheet("color: red;")
        self.connection_status_changed.emit(connected)

    def closeEvent(self, event: Any) -> None:
        """Handle window close event."""
        if not self._confirm_discard():
            event.ignore()
            return
        event.accept()

        # Close gRPC client
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass

        # Stop local server
        if self._server_manager is not None:
            self._server_manager.stop()
