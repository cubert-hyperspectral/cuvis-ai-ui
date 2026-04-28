"""Node palette widget for browsing and selecting nodes.

This module provides a searchable tree widget that displays available
cuvis-ai nodes organized by NodeCategory. Users can drag nodes from the
palette onto the graph canvas to create new node instances.
"""

from typing import Any

from loguru import logger
from NodeGraphQt import NodeGraph
from PySide6.QtCore import QByteArray, QRect, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QDrag, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QMimeData

from cuvis_ai_schemas.enums import NodeCategory, NodeTag
from cuvis_ai_schemas.extensions.ui.node_display import TAG_STYLES
from cuvis_ai_schemas.grpc.conversions import proto_to_node_category, proto_to_node_tag

from ..adapters import NodeRegistry, PortSpec
from ..adapters.node_adapter import category_color, tag_chip_color
from .tag_filter import TagFilterWidget


class NodePaletteDelegate(QStyledItemDelegate):
    """Paints tag chips to the right of the class name for NodePaletteItem rows."""

    _CHIP_H = 14
    _CHIP_PAD = 4
    _CHIP_MARGIN = 3
    _FONT_SIZE = 8

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: Any,
    ) -> None:
        super().paint(painter, option, index)
        chips = index.data(Qt.ItemDataRole.UserRole + 1)
        if not chips:
            return
        font = painter.font()
        font.setPointSize(self._FONT_SIZE)
        painter.setFont(font)
        x = option.rect.right() - self._CHIP_MARGIN
        y = option.rect.center().y() - self._CHIP_H // 2
        for label, (r, g, b, a) in reversed(chips):
            fm = painter.fontMetrics()
            w = fm.horizontalAdvance(label) + self._CHIP_PAD * 2
            x -= w + self._CHIP_MARGIN
            rect = QRect(x, y, w, self._CHIP_H)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(r, g, b, a))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(QColor(255, 255, 255, 230))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
            painter.restore()


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

        # Chip data stored for the delegate to paint inline
        chips: list[tuple[str, tuple[int, int, int, int]]] = []
        for raw in node_info.get("tags", []):
            tag = proto_to_node_tag(raw)
            if tag is None:
                continue
            short = TAG_STYLES.get(tag, {}).get("short_label", "")
            if short:
                chips.append((short, tag_chip_color(tag)))
        self.setData(0, Qt.ItemDataRole.UserRole + 1, chips)

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


class NodePalette(QWidget):
    """Searchable tree widget for browsing available nodes.

    Features:
    - Tree grouped by NodeCategory (enum-int order)
    - Tag filter strip for narrowing by modality / task / lifecycle / properties / backend
    - Search filter matching class name, full path, and tag short-labels
    - Category-coloured backgrounds, SVG icons, and inline tag chips
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
        self._active_tags: dict[str, set[NodeTag]] = {}

        self._setup_ui()
        self._populate_tree()

    def _setup_ui(self) -> None:
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Tag filter strip (above search bar)
        self._tag_filter = TagFilterWidget()
        self._tag_filter.filter_changed.connect(self._on_filter_changed)
        layout.addWidget(self._tag_filter)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(4)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search nodes...")
        self._search_input.textChanged.connect(lambda _: self._apply_filters())
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
        self._tree.setItemDelegate(NodePaletteDelegate(self._tree))

        # Enable custom drag handling
        self._tree.startDrag = self._start_drag  # type: ignore

        layout.addWidget(self._tree)

    def _apply_filters(self) -> None:
        """Apply active tag filter and search text, then rebuild the tree."""
        search = self._search_input.text().lower().strip()

        # Tag filter: OR-within-namespace, AND-across-namespaces
        filtered = TagFilterWidget.filter_nodes(self._all_nodes, self._active_tags)

        # Search filter on the tag-filtered subset
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

    def _on_filter_changed(self, active_tags: dict[str, set[NodeTag]]) -> None:
        self._active_tags = active_tags
        self._apply_filters()

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
        class_path = node_info.get("full_path", "")
        node_class = self._registry.get_node_class(class_path)

        if node_class is None:
            logger.warning(f"Node class not found: {class_path}")
            return

        try:
            node_id = f"{node_class.__identifier__}.{node_class.__name__}"
            node = self._graph.create_node(node_id)

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
