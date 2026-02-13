"""Node palette widget for browsing and selecting nodes.

This module provides a searchable tree widget that displays available
cuvis-ai nodes organized by category/plugin. Users can drag nodes
from the palette onto the graph canvas to create new node instances.
"""

from typing import Any

from loguru import logger
from NodeGraphQt import NodeGraph
from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..adapters import NodeRegistry, PortSpec


class NodePaletteItem(QTreeWidgetItem):
    """Tree item representing a node type.

    Stores the node info dictionary for drag-and-drop creation.
    """

    def __init__(
        self,
        parent: QTreeWidgetItem | QTreeWidget,
        node_info: dict[str, Any],
    ) -> None:
        """Initialize the item.

        Args:
            parent: Parent tree item or widget
            node_info: Node information dictionary
        """
        super().__init__(parent)
        self.node_info = node_info

        # Display name
        class_name = node_info.get("class_name", "Unknown")
        self.setText(0, class_name)

        # Tooltip with details
        self.setToolTip(0, self._format_tooltip())

    def _format_tooltip(self) -> str:
        """Format a detailed tooltip for the node."""
        info = self.node_info
        lines = [f"<b>{info.get('class_name', 'Unknown')}</b>"]

        full_path = info.get("full_path", "")
        if full_path:
            lines.append(f"<i>{full_path}</i>")

        lines.append("")

        # Input specs
        input_specs = info.get("input_specs", [])
        if input_specs:
            lines.append("<b>Inputs:</b>")
            for spec in input_specs:
                if isinstance(spec, dict):
                    name = spec.get("name", "?")
                    dtype = spec.get("dtype", "any")
                    optional = spec.get("optional", False)
                    opt_str = " (opt)" if optional else ""
                    lines.append(f"  - {name}: {dtype}{opt_str}")
                elif isinstance(spec, PortSpec):
                    opt_str = " (opt)" if spec.optional else ""
                    lines.append(f"  - {spec.name}: {spec.dtype}{opt_str}")

        # Output specs
        output_specs = info.get("output_specs", [])
        if output_specs:
            lines.append("<b>Outputs:</b>")
            for spec in output_specs:
                if isinstance(spec, dict):
                    name = spec.get("name", "?")
                    dtype = spec.get("dtype", "any")
                    lines.append(f"  - {name}: {dtype}")
                elif isinstance(spec, PortSpec):
                    lines.append(f"  - {spec.name}: {spec.dtype}")

        # Source info
        source = info.get("source", "")
        plugin = info.get("plugin_name", "")
        if source or plugin:
            lines.append("")
            if plugin:
                lines.append(f"Plugin: {plugin}")
            elif source:
                lines.append(f"Source: {source}")

        return "<br>".join(lines)


class NodePalette(QWidget):
    """Searchable tree widget for browsing available nodes.

    Features:
    - Tree view organized by category/plugin
    - Search filter with real-time filtering
    - Drag-and-drop to create nodes on canvas
    - Refresh button to reload from server

    Signals:
        node_double_clicked: Emitted when a node is double-clicked (node_info: dict)
        refresh_requested: Emitted when refresh button is clicked
    """

    node_double_clicked = Signal(dict)
    refresh_requested = Signal()

    def __init__(
        self,
        node_registry: NodeRegistry,
        graph: NodeGraph,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the node palette.

        Args:
            node_registry: Registry of available nodes
            graph: NodeGraphQt graph for node creation
            parent: Parent widget
        """
        super().__init__(parent)

        self._registry = node_registry
        self._graph = graph

        self._setup_ui()
        self._populate_tree()

    def _setup_ui(self) -> None:
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(4)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search nodes...")
        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_input.setClearButtonEnabled(True)
        search_layout.addWidget(self._search_input)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMaximumWidth(70)
        refresh_btn.clicked.connect(self._on_refresh_clicked)
        search_layout.addWidget(refresh_btn)

        layout.addLayout(search_layout)

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("Available Nodes")
        self._tree.setDragEnabled(True)
        self._tree.setDragDropMode(QTreeWidget.DragDropMode.DragOnly)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        # Enable custom drag handling
        self._tree.startDrag = self._start_drag  # type: ignore

        layout.addWidget(self._tree)

    def _populate_tree(self) -> None:
        """Populate the tree with nodes from the registry."""
        self._tree.clear()

        # Group nodes by category
        categories = self._registry.get_nodes_by_category()

        # Sort categories alphabetically, but put "Builtin" first
        sorted_cats = sorted(categories.keys())
        if "Builtin" in sorted_cats:
            sorted_cats.remove("Builtin")
            sorted_cats.insert(0, "Builtin")

        for category in sorted_cats:
            nodes = categories[category]
            if not nodes:
                continue

            # Create category item
            cat_item = QTreeWidgetItem(self._tree)
            cat_item.setText(0, f"{category} ({len(nodes)})")
            cat_item.setFlags(
                cat_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled
            )

            # Add node items
            for node_info in sorted(nodes, key=lambda n: n.get("class_name", "")):
                NodePaletteItem(cat_item, node_info)

            cat_item.setExpanded(True)

    def _on_search_changed(self, text: str) -> None:
        """Handle search text change.

        Args:
            text: Search text
        """
        search_lower = text.lower().strip()

        # Show all if empty
        if not search_lower:
            self._show_all_items()
            return

        # Filter items
        for i in range(self._tree.topLevelItemCount()):
            cat_item = self._tree.topLevelItem(i)
            if cat_item is None:
                continue

            visible_count = 0
            for j in range(cat_item.childCount()):
                node_item = cat_item.child(j)
                if node_item is None:
                    continue

                # Check if node matches search
                if isinstance(node_item, NodePaletteItem):
                    class_name = node_item.node_info.get("class_name", "").lower()
                    full_path = node_item.node_info.get("full_path", "").lower()
                    matches = search_lower in class_name or search_lower in full_path
                else:
                    matches = search_lower in node_item.text(0).lower()

                node_item.setHidden(not matches)
                if matches:
                    visible_count += 1

            # Hide category if no matches
            cat_item.setHidden(visible_count == 0)
            cat_item.setExpanded(True)

    def _show_all_items(self) -> None:
        """Show all items in the tree."""
        for i in range(self._tree.topLevelItemCount()):
            cat_item = self._tree.topLevelItem(i)
            if cat_item is None:
                continue
            cat_item.setHidden(False)
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                if child:
                    child.setHidden(False)

    def _on_refresh_clicked(self) -> None:
        """Handle refresh button click."""
        self.refresh_requested.emit()
        self._populate_tree()

    def _on_item_double_clicked(
        self, item: QTreeWidgetItem, column: int
    ) -> None:
        """Handle item double-click.

        Args:
            item: Clicked item
            column: Clicked column
        """
        if isinstance(item, NodePaletteItem):
            self.node_double_clicked.emit(item.node_info)
            self._create_node(item.node_info)

    def _start_drag(self, supported_actions: Qt.DropAction) -> None:
        """Start a drag operation with the selected node.

        Args:
            supported_actions: Supported drop actions
        """
        item = self._tree.currentItem()
        if not isinstance(item, NodePaletteItem):
            return

        # Create drag with node info
        drag = QDrag(self)
        mime_data = QMimeData()

        # Store the class path in mime data
        class_path = item.node_info.get("full_path", "")
        mime_data.setText(class_path)
        mime_data.setData("application/x-cuvis-node", class_path.encode())

        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction)

    def _create_node(self, node_info: dict[str, Any]) -> None:
        """Create a node on the graph from node info.

        Args:
            node_info: Node information dictionary
        """
        class_path = node_info.get("full_path", "")
        node_class = self._registry.get_node_class(class_path)

        if node_class is None:
            logger.warning(f"Node class not found: {class_path}")
            return

        try:
            # NodeGraphQt uses __identifier__ + '.' + class.__name__ for lookup
            # (not NODE_NAME which is just for display)
            node_id = f"{node_class.__identifier__}.{node_class.__name__}"
            node = self._graph.create_node(node_id)

            # Position at view center
            view = self._graph.viewer()
            if view:
                center = view.mapToScene(view.viewport().rect().center())
                node.set_pos(center.x(), center.y())

            logger.info(f"Created node: {node_info.get('class_name')}")
        except Exception as e:
            logger.error(f"Failed to create node: {e}")

    def refresh_nodes(self, nodes: list[dict[str, Any]]) -> None:
        """Refresh the palette with new node list.

        Args:
            nodes: List of node info dictionaries
        """
        self._registry.clear()
        self._registry.register_nodes(nodes)
        self._populate_tree()
        logger.info(f"Refreshed palette with {len(nodes)} nodes")

    def get_selected_node_info(self) -> dict[str, Any] | None:
        """Get the currently selected node info.

        Returns:
            Node info dictionary or None
        """
        item = self._tree.currentItem()
        if isinstance(item, NodePaletteItem):
            return item.node_info
        return None
