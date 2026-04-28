"""Collapsible tag filter strip for the node palette."""

from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from cuvis_ai_schemas.enums import NodeTag
from cuvis_ai_schemas.extensions.ui.node_display import TAG_STYLES
from cuvis_ai_schemas.grpc.conversions import proto_to_node_tag

# Ordered sub-namespaces with their member tags.
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


class TagFilterWidget(QWidget):
    """Collapsible filter strip with one group per tag sub-namespace.

    Emits ``filter_changed`` with a ``dict[str, set[NodeTag]]`` whenever the
    active selection changes.  Semantics: OR within a namespace, AND across
    namespaces — a node must match at least one active tag in every namespace
    that has active selections.
    """

    filter_changed = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active: dict[str, set[NodeTag]] = {ns: set() for ns in _TAG_NAMESPACES}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)

        for ns, tags in _TAG_NAMESPACES.items():
            layout.addWidget(_TagGroup(ns, tags, self._on_chip_toggled))

    def _on_chip_toggled(self, namespace: str, tag: NodeTag, active: bool) -> None:
        if active:
            self._active[namespace].add(tag)
        else:
            self._active[namespace].discard(tag)
        self.filter_changed.emit({k: set(v) for k, v in self._active.items()})

    @staticmethod
    def filter_nodes(
        all_nodes: list[dict[str, Any]],
        active_tags_by_namespace: dict[str, set[NodeTag]],
    ) -> list[dict[str, Any]]:
        """Return the subset of *all_nodes* that passes the active tag filter.

        Returns *all_nodes* unchanged when no namespace has active selections.
        """
        if not any(active_tags_by_namespace.values()):
            return all_nodes
        out = []
        for info in all_nodes:
            node_tags = {proto_to_node_tag(t) for t in info.get("tags", [])}
            node_tags.discard(None)
            keep = all(
                not ns_tags or bool(node_tags & ns_tags)
                for ns_tags in active_tags_by_namespace.values()
            )
            if keep:
                out.append(info)
        return out


class _TagGroup(QFrame):
    """Collapsible group of chip-buttons for one tag namespace."""

    def __init__(
        self,
        namespace: str,
        tags: list[NodeTag],
        on_toggle: Callable[[str, NodeTag, bool], None],
    ) -> None:
        super().__init__()
        self._namespace = namespace
        self._on_toggle = on_toggle
        self._collapsed = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(1)

        # Header with collapse toggle
        header = QHBoxLayout()
        self._toggle_btn = QPushButton(f"▾ {namespace}")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        header.addWidget(self._toggle_btn)
        header.addStretch()
        outer.addLayout(header)

        # Chips in a horizontal scroll area so Modality (16 chips) doesn't overflow
        scroll = QScrollArea()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(30)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        chip_widget = QWidget()
        chip_layout = QHBoxLayout(chip_widget)
        chip_layout.setContentsMargins(2, 0, 2, 0)
        chip_layout.setSpacing(3)

        for tag in tags:
            short = TAG_STYLES.get(tag, {}).get("short_label", tag.value)
            btn = QPushButton(short)
            btn.setCheckable(True)
            btn.setFixedHeight(20)
            btn.toggled.connect(lambda checked, t=tag: self._on_toggle(self._namespace, t, checked))
            chip_layout.addWidget(btn)
        chip_layout.addStretch()

        scroll.setWidget(chip_widget)
        self._chips_scroll = scroll
        outer.addWidget(scroll)

    def _toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        self._chips_scroll.setVisible(not self._collapsed)
        arrow = "▸" if self._collapsed else "▾"
        self._toggle_btn.setText(f"{arrow} {self._namespace}")
