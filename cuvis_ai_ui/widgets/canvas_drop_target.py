"""Drop target that turns palette drags into nodes on the canvas.

Installed as an event filter on the NodeGraphQt viewer's viewport. Listens
for drags carrying the ``application/x-cuvis-node`` MIME type (set by
:meth:`NodePalette._start_drag`) and creates a node at the drop position.
"""

from typing import Any

from loguru import logger
from NodeGraphQt import NodeGraph
from PySide6.QtCore import QEvent, QObject

from ..adapters import NodeRegistry
from .node_palette import create_node_on_graph


class CanvasDropTarget(QObject):
    """Accepts node drops on the NodeGraphQt viewer."""

    MIME = "application/x-cuvis-node"

    def __init__(
        self,
        viewer: Any,
        graph: NodeGraph,
        registry: NodeRegistry,
    ) -> None:
        super().__init__(viewer)
        self._viewer = viewer
        self._graph = graph
        self._registry = registry

    def install(self) -> None:
        """Enable drops on the viewer and start listening."""
        self._viewer.setAcceptDrops(True)
        viewport = self._viewer.viewport()
        viewport.setAcceptDrops(True)
        viewport.installEventFilter(self)

    def eventFilter(self, obj: Any, event: Any) -> bool:  # type: ignore[override]
        et = event.type()

        if et in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if event.mimeData().hasFormat(self.MIME):
                event.acceptProposedAction()
                return True
            return False

        if et == QEvent.Type.Drop:
            md = event.mimeData()
            if not md.hasFormat(self.MIME):
                return False

            class_path = bytes(md.data(self.MIME)).decode("utf-8")
            # QDropEvent.position() returns QPointF on Qt6; pos() is the legacy alias.
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            scene = self._viewer.mapToScene(pos)

            node = create_node_on_graph(
                self._graph,
                self._registry,
                class_path,
                (scene.x(), scene.y()),
            )
            if node is None:
                logger.warning(f"Drop ignored: could not create node for {class_path!r}")
                return False

            event.acceptProposedAction()
            return True

        return False
