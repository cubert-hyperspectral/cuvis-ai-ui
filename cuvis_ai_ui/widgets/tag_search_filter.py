"""Unified search-and-tag-filter widget for the node palette.

Replaces the multi-namespace TagFilterWidget + standalone search bar with a
single QLineEdit that:

- Suggests tag short-labels (and full enum names) via QCompleter as the user types
- Promotes a picked completion to an active filter chip; free text remains as
  text search
- Renders active chips above the input with × buttons and a Clear-all button

Filter semantic for chips: OR within tag namespace, AND across namespaces
(matches ALL-5187 phase 06). Namespaces are not surfaced in the UI — picking
'hsi' + 'msi' returns nodes that are HSI or MSI; adding 'seg' narrows to
(HSI or MSI) and segmentation.
"""

from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCompleter,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cuvis_ai_schemas.enums import NodeTag
from cuvis_ai_schemas.extensions.ui.node_display import TAG_STYLES
from cuvis_ai_schemas.grpc.conversions import proto_to_node_tag

from ..adapters.node_adapter import tag_chip_color


_TAG_NAMESPACES: dict[str, list[NodeTag]] = {
    "Modality": [
        NodeTag.IMAGE,
        NodeTag.VIDEO,
        NodeTag.RGB,
        NodeTag.MULTISPECTRAL,
        NodeTag.HYPERSPECTRAL,
        NodeTag.POINT_CLOUD,
        NodeTag.DEPTH,
        NodeTag.MASK,
        NodeTag.BBOX,
        NodeTag.KEYPOINTS,
        NodeTag.TEXT,
        NodeTag.AUDIO,
        NodeTag.TABULAR,
        NodeTag.TIME_SERIES,
        NodeTag.METADATA,
        NodeTag.EMBEDDING,
    ],
    "Task": [
        NodeTag.CLASSIFICATION,
        NodeTag.SEGMENTATION,
        NodeTag.DETECTION,
        NodeTag.TRACKING,
        NodeTag.REGRESSION,
        NodeTag.GENERATION,
        NodeTag.RECONSTRUCTION,
        NodeTag.DENOISING,
        NodeTag.UNMIXING,
        NodeTag.DIM_REDUCTION,
        NodeTag.CLUSTERING,
        NodeTag.ANOMALY,
        NodeTag.RETRIEVAL,
    ],
    "Lifecycle": [
        NodeTag.PREPROCESSING,
        NodeTag.POSTPROCESSING,
        NodeTag.AUGMENTATION,
        NodeTag.CALIBRATION,
        NodeTag.NORMALIZATION,
        NodeTag.TRAINING,
        NodeTag.EVALUATION,
        NodeTag.INFERENCE,
    ],
    "Properties": [
        NodeTag.LEARNABLE,
        NodeTag.DIFFERENTIABLE,
        NodeTag.STOCHASTIC,
        NodeTag.INVERTIBLE,
        NodeTag.STREAMING,
        NodeTag.BATCHED,
        NodeTag.STATEFUL,
    ],
    "Backend": [
        NodeTag.TORCH,
        NodeTag.NUMPY,
        NodeTag.JAX,
        NodeTag.ONNX,
    ],
}

_TAG_TO_NAMESPACE: dict[NodeTag, str] = {
    tag: ns for ns, tags in _TAG_NAMESPACES.items() for tag in tags
}


def _build_completer_entries() -> tuple[list[str], dict[str, NodeTag]]:
    """Return ``(sorted display strings, lower-cased lookup map)`` for QCompleter.

    Each tag contributes both its ``short_label`` (e.g. ``"hsi"``) and its
    enum value (e.g. ``"hyperspectral"``) so either matches.
    """
    entries: list[str] = []
    lookup: dict[str, NodeTag] = {}
    for tag in NodeTag:
        if tag is NodeTag.UNSPECIFIED:
            continue
        styles = TAG_STYLES.get(tag, {})
        for entry in (styles.get("short_label", ""), tag.value):
            key = entry.lower()
            if entry and key not in lookup:
                lookup[key] = tag
                entries.append(entry)
    entries.sort()
    return entries, lookup


class TagSearchFilter(QWidget):
    """Unified search + tag-filter input for the node palette.

    Signals:
        tags_changed (set[NodeTag]): Emitted when active chips change.
        text_changed (str): Emitted when free-text input changes.
    """

    tags_changed = Signal(set)
    text_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._active_tags: set[NodeTag] = set()
        self._chips: dict[NodeTag, _Chip] = {}
        self._completer_entries, self._completer_lookup = _build_completer_entries()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Active-chip row, hidden until the first chip is added.
        self._chips_row = QWidget()
        self._chips_layout = QHBoxLayout(self._chips_row)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(3)
        self._chips_layout.addStretch()
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFlat(True)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet(
            "QPushButton { color: #4E7BD4; border: none; padding: 0 4px; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        self._clear_btn.clicked.connect(self.clear_tags)
        self._chips_layout.addWidget(self._clear_btn)
        self._chips_row.setVisible(False)
        layout.addWidget(self._chips_row)

        # Input row: QLineEdit + slot for trailing widgets (e.g. Refresh button).
        input_row_widget = QWidget()
        self._input_row = QHBoxLayout(input_row_widget)
        self._input_row.setContentsMargins(0, 0, 0, 0)
        self._input_row.setSpacing(4)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search nodes or type a tag (hsi, seg, train, …)")
        self._input.setClearButtonEnabled(True)

        completer = QCompleter(self._completer_entries, self._input)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.activated.connect(self._on_completer_activated)
        self._input.setCompleter(completer)

        self._input.textChanged.connect(lambda text: self.text_changed.emit(text.strip()))
        self._input_row.addWidget(self._input)
        layout.addWidget(input_row_widget)

    # Public API -------------------------------------------------------------

    def current_tags(self) -> set[NodeTag]:
        return set(self._active_tags)

    def current_text(self) -> str:
        return self._input.text().strip()

    def add_trailing_widget(self, widget: QWidget) -> None:
        """Append a widget to the right of the input (e.g. a Refresh button)."""
        self._input_row.addWidget(widget)

    def clear_tags(self) -> None:
        if not self._active_tags:
            return
        for tag in list(self._active_tags):
            self._remove_chip_widget(tag)
        self._active_tags.clear()
        self._chips_row.setVisible(False)
        self.tags_changed.emit(set())

    # Internals --------------------------------------------------------------

    def _on_completer_activated(self, text: str) -> None:
        tag = self._completer_lookup.get(text.lower())
        # Always clear input so the user can type the next tag immediately.
        self._input.clear()
        if tag is None or tag in self._active_tags:
            return
        self._active_tags.add(tag)
        self._add_chip_widget(tag)
        self._chips_row.setVisible(True)
        self.tags_changed.emit(set(self._active_tags))

    def _add_chip_widget(self, tag: NodeTag) -> None:
        chip = _Chip(tag, on_remove=self._on_chip_removed)
        # Insert before the trailing stretch + Clear button (last 2 items).
        self._chips_layout.insertWidget(self._chips_layout.count() - 2, chip)
        self._chips[tag] = chip

    def _remove_chip_widget(self, tag: NodeTag) -> None:
        chip = self._chips.pop(tag, None)
        if chip is not None:
            self._chips_layout.removeWidget(chip)
            chip.deleteLater()

    def _on_chip_removed(self, tag: NodeTag) -> None:
        if tag not in self._active_tags:
            return
        self._active_tags.discard(tag)
        self._remove_chip_widget(tag)
        if not self._active_tags:
            self._chips_row.setVisible(False)
        self.tags_changed.emit(set(self._active_tags))

    # Filter logic -----------------------------------------------------------

    @staticmethod
    def filter_nodes(
        all_nodes: list[dict[str, Any]],
        active_tags: set[NodeTag],
    ) -> list[dict[str, Any]]:
        """Filter *all_nodes* by *active_tags* using OR-within / AND-across.

        Active tags are bucketed by namespace internally; a node is kept iff
        it has ≥1 tag in every active namespace. Returns *all_nodes* unchanged
        when no tags are active.
        """
        if not active_tags:
            return all_nodes

        by_ns: dict[str, set[NodeTag]] = {}
        for tag in active_tags:
            ns = _TAG_TO_NAMESPACE.get(tag)
            if ns is None:
                continue
            by_ns.setdefault(ns, set()).add(tag)
        if not by_ns:
            return all_nodes

        out: list[dict[str, Any]] = []
        for info in all_nodes:
            node_tags = {proto_to_node_tag(t) for t in info.get("tags", [])}
            node_tags.discard(None)
            if all(bool(node_tags & ns_tags) for ns_tags in by_ns.values()):
                out.append(info)
        return out


class _Chip(QPushButton):
    """Single tag chip — clicking removes it via the supplied callback."""

    def __init__(
        self,
        tag: NodeTag,
        on_remove: Callable[[NodeTag], None],
    ) -> None:
        short = TAG_STYLES.get(tag, {}).get("short_label", tag.value)
        super().__init__(f"{short}  ×")
        self.tag = tag

        r, g, b, _ = tag_chip_color(tag)
        self.setStyleSheet(
            f"QPushButton {{ background-color: rgba({r}, {g}, {b}, 220); "
            f"color: white; border: none; border-radius: 8px; "
            f"padding: 2px 6px; font-size: 10px; }} "
            f"QPushButton:hover {{ background-color: rgba({r}, {g}, {b}, 255); }}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Remove filter: {tag.value}")
        self.clicked.connect(lambda: on_remove(tag))
