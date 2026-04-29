"""Node palette widget for browsing and selecting nodes.

This module provides a searchable tree widget that displays available
cuvis-ai nodes organized by NodeCategory. Users can drag nodes from the
palette onto the graph canvas to create new node instances.
"""

from typing import Any

from loguru import logger
from NodeGraphQt import NodeGraph
from PySide6.QtCore import QByteArray, QMimeData, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QDrag, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cuvis_ai_schemas.enums import NodeCategory
from cuvis_ai_schemas.extensions.ui.node_display import TAG_STYLES
from cuvis_ai_schemas.grpc.conversions import proto_to_node_category, proto_to_node_tag

from ..adapters import NodeRegistry, PortSpec
from ..adapters.node_adapter import category_color
from .tag_search_filter import TagSearchFilter


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

        class_name = node_info.get("class_name", "Unknown")
        self.setText(0, class_name)
        self.setToolTip(0, self._format_tooltip())

        # Category background colour
        cat = proto_to_node_category(node_info.get("category", 0))
        r, g, b, a = category_color(cat)
        self.setBackground(0, QBrush(QColor(r, g, b, a)))

        # SVG icon — empty bytes means no icon, no fallback
        svg_bytes = node_info.get("icon_svg", b"")
        if svg_bytes:
            renderer = QSvgRenderer(QByteArray(svg_bytes))
            pixmap = QPixmap(QSize(24, 24))
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            self.setIcon(0, QIcon(pixmap))

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
                    lines.append(f"  - {spec.dtype}{opt_str}")

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
                    lines.append(f"  - {spec.dtype}")

        # Source info
        source = info.get("source", "")
        plugin = info.get("plugin_name", "")
        if source or plugin:
            lines.append("")
            if plugin:
                lines.append(f"Plugin: {plugin}")
            elif source:
                lines.append(f"Source: {source}")

        # Category + tags
        cat = proto_to_node_category(info.get("category", 0))
        lines.append(f"Category: {cat.get_display_name()}")

        tag_labels: list[str] = []
        for raw in info.get("tags", []):
            tag = proto_to_node_tag(raw)
            if tag:
                tag_labels.append(TAG_STYLES.get(tag, {}).get("short_label", tag.value))
        if tag_labels:
            lines.append(f"Tags: {', '.join(tag_labels)}")

        return "<br>".join(lines)


def create_node_on_graph(
    graph: NodeGraph,
    registry: NodeRegistry,
    class_path: str,
    scene_pos: tuple[float, float] | None = None,
) -> Any:
    """Place a node on the graph by full class path.

    Resolves ``class_path`` through ``registry``, creates the corresponding
    NodeGraphQt node, and positions it. When ``scene_pos`` is ``None``,
    falls back to the viewport center (legacy double-click behaviour).

    Args:
        graph: Target NodeGraphQt graph.
        registry: Node registry that maps class paths to node classes.
        class_path: Full Python path of the node class (e.g. ``cuvis_ai.node.X``).
        scene_pos: Optional ``(x, y)`` in scene coordinates for the placed node.

    Returns:
        The created node, or ``None`` if the class could not be resolved.
    """
    if not class_path:
        logger.warning("create_node_on_graph called with empty class_path")
        return None

    node_class = registry.get_node_class(class_path)
    if node_class is None:
        logger.warning(f"Node class not found: {class_path}")
        return None

    try:
        node_id = f"{node_class.__identifier__}.{node_class.__name__}"
        node = graph.create_node(node_id)

        if scene_pos is not None:
            node.set_pos(scene_pos[0], scene_pos[1])
        else:
            view = graph.viewer()
            if view:
                center = view.mapToScene(view.viewport().rect().center())
                node.set_pos(center.x(), center.y())

        logger.info(f"Created node: {node_class.__name__}")
        return node
    except Exception as e:
        logger.error(f"Failed to create node: {e}")
        return None


class NodePalette(QWidget):
    """Searchable tree widget for browsing available nodes.

    Features:
    - Tree grouped by NodeCategory (enum-int order)
    - Unified search-and-tag-filter input (autocompletes tags, free-text falls
      through as class-name / full-path / tag-label search)
    - Category-coloured backgrounds, SVG icons; tag list shown in tooltip
    - Drag-and-drop to create nodes on canvas

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

        # Full unfiltered list — seeded from the registry so the initial
        # render is correct even before refresh_nodes() is called.
        self._all_nodes: list[dict[str, Any]] = list(node_registry.get_all_nodes())

        self._setup_ui()
        self._populate_tree()

    def _setup_ui(self) -> None:
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Unified search-and-tag input (chips + autocomplete + free text)
        self._search = TagSearchFilter()
        self._search.tags_changed.connect(lambda _tags: self._apply_filters())
        self._search.text_changed.connect(lambda _text: self._apply_filters())

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMaximumWidth(70)
        refresh_btn.clicked.connect(self._on_refresh_clicked)
        self._search.add_trailing_widget(refresh_btn)

        layout.addWidget(self._search)

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("Available Nodes")
        self._tree.setDragEnabled(True)
        self._tree.setDragDropMode(QTreeWidget.DragDropMode.DragOnly)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        # Enable custom drag handling
        self._tree.startDrag = self._start_drag  # type: ignore

        layout.addWidget(self._tree)

    def _apply_filters(self) -> None:
        """Apply active tag chips and free-text input, then rebuild the tree."""
        active_tags = self._search.current_tags()
        search = self._search.current_text().lower()

        filtered = TagSearchFilter.filter_nodes(self._all_nodes, active_tags)

        if search:

            def _matches(info: dict[str, Any]) -> bool:
                class_name = info.get("class_name", "").lower()
                full_path = info.get("full_path", "").lower()
                tag_text = " ".join(
                    TAG_STYLES.get(proto_to_node_tag(t), {}).get("short_label", "")
                    for t in info.get("tags", [])
                    if proto_to_node_tag(t) is not None
                ).lower()
                return search in class_name or search in full_path or search in tag_text

            filtered = [n for n in filtered if _matches(n)]

        self._populate_tree(filtered)

    def _populate_tree(self, nodes: list[dict[str, Any]] | None = None) -> None:
        """Populate the tree with nodes grouped by NodeCategory."""
        self._tree.clear()

        source = nodes if nodes is not None else self._all_nodes
        grouped = self._registry.group_by_category(source)

        for category in NodeCategory:  # enum-int order = canonical render order
            cat_nodes = grouped.get(category, [])
            if not cat_nodes:
                continue

            cat_item = QTreeWidgetItem(self._tree)
            cat_item.setText(0, f"{category.get_display_name()} ({len(cat_nodes)})")
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)

            for node_info in sorted(cat_nodes, key=lambda n: n.get("class_name", "")):
                NodePaletteItem(cat_item, node_info)

            cat_item.setExpanded(True)

    def _on_refresh_clicked(self) -> None:
        """Handle refresh button click."""
        self.refresh_requested.emit()
        self._populate_tree()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
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

        drag = QDrag(self)
        mime_data = QMimeData()

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
        create_node_on_graph(
            self._graph,
            self._registry,
            node_info.get("full_path", ""),
        )

    def refresh_nodes(self, nodes: list[dict[str, Any]]) -> None:
        """Refresh the palette with new node list.

        Args:
            nodes: List of node info dictionaries
        """
        self._registry.clear()
        self._registry.register_nodes(nodes)
        self._all_nodes = list(self._registry.get_all_nodes())
        self._apply_filters()
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
