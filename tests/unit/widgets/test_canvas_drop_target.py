"""Unit tests for CanvasDropTarget event filter.

The widget intercepts QDrag/QDrop events on the NodeGraphQt viewer viewport
and forwards Drop events carrying ``application/x-cuvis-node`` to
``create_node_on_graph``. Tests construct events as ``MagicMock`` and call
``eventFilter()`` directly — no real Qt drag-and-drop machinery needed.
"""

from unittest.mock import MagicMock, patch

from PySide6.QtCore import QEvent, QPointF
from PySide6.QtWidgets import QWidget

from cuvis_ai_ui.widgets.canvas_drop_target import CanvasDropTarget


def _make_drop_target():
    """Build a CanvasDropTarget with a real QWidget viewer + mocked methods.

    ``super().__init__(viewer)`` requires a real QObject as parent, so the
    viewer is a QWidget. The methods the widget actually calls on the viewer
    (``setAcceptDrops``, ``viewport``, ``mapToScene``) are then replaced with
    MagicMocks so we can assert on them.
    """
    viewer = QWidget()
    viewport = MagicMock()
    viewer.setAcceptDrops = MagicMock()
    viewer.viewport = MagicMock(return_value=viewport)
    viewer.mapToScene = MagicMock(return_value=QPointF(0.0, 0.0))
    graph = MagicMock()
    registry = MagicMock()
    target = CanvasDropTarget(viewer, graph, registry)
    return target, viewer, viewport, graph, registry


def _make_event(event_type: QEvent.Type, *, mime_match: bool = True, mime_data: bytes = b""):
    event = MagicMock()
    event.type.return_value = event_type
    md = MagicMock()
    md.hasFormat.return_value = mime_match
    md.data.return_value = mime_data
    event.mimeData.return_value = md
    return event


def test_install_enables_drops_and_filters_viewport(qapp):
    target, viewer, viewport, _graph, _registry = _make_drop_target()

    target.install()

    viewer.setAcceptDrops.assert_called_once_with(True)
    viewport.setAcceptDrops.assert_called_once_with(True)
    viewport.installEventFilter.assert_called_once_with(target)


def test_drag_enter_with_matching_mime_accepts(qapp):
    target, _viewer, viewport, _graph, _registry = _make_drop_target()
    event = _make_event(QEvent.Type.DragEnter, mime_match=True)

    result = target.eventFilter(viewport, event)

    assert result is True
    event.acceptProposedAction.assert_called_once()


def test_drag_move_with_matching_mime_accepts(qapp):
    target, _viewer, viewport, _graph, _registry = _make_drop_target()
    event = _make_event(QEvent.Type.DragMove, mime_match=True)

    result = target.eventFilter(viewport, event)

    assert result is True
    event.acceptProposedAction.assert_called_once()


def test_drag_enter_with_wrong_mime_rejects(qapp):
    target, _viewer, viewport, _graph, _registry = _make_drop_target()
    event = _make_event(QEvent.Type.DragEnter, mime_match=False)

    result = target.eventFilter(viewport, event)

    assert result is False
    event.acceptProposedAction.assert_not_called()


@patch("cuvis_ai_ui.widgets.canvas_drop_target.create_node_on_graph")
def test_drop_creates_node_at_scene_position(mock_create, qapp):
    mock_create.return_value = object()  # Any non-None value
    target, viewer, viewport, graph, registry = _make_drop_target()
    viewer.mapToScene.return_value = QPointF(42.0, 17.5)

    event = _make_event(QEvent.Type.Drop, mime_match=True, mime_data=b"my.module.MyNode")
    event.position.return_value = QPointF(100.0, 200.0)

    result = target.eventFilter(viewport, event)

    assert result is True
    event.acceptProposedAction.assert_called_once()
    mock_create.assert_called_once()
    args = mock_create.call_args[0]
    assert args[0] is graph
    assert args[1] is registry
    assert args[2] == "my.module.MyNode"
    # Scene coordinates from mapToScene return value
    assert args[3] == (42.0, 17.5)


@patch("cuvis_ai_ui.widgets.canvas_drop_target.create_node_on_graph")
def test_drop_with_wrong_mime_ignored(mock_create, qapp):
    target, _viewer, viewport, _graph, _registry = _make_drop_target()
    event = _make_event(QEvent.Type.Drop, mime_match=False)

    result = target.eventFilter(viewport, event)

    assert result is False
    mock_create.assert_not_called()
    event.acceptProposedAction.assert_not_called()


@patch("cuvis_ai_ui.widgets.canvas_drop_target.create_node_on_graph")
def test_drop_returns_false_when_create_fails(mock_create, qapp):
    mock_create.return_value = None
    target, viewer, viewport, _graph, _registry = _make_drop_target()
    viewer.mapToScene.return_value = QPointF(0.0, 0.0)

    event = _make_event(QEvent.Type.Drop, mime_match=True, mime_data=b"missing.Class")
    event.position.return_value = QPointF(0.0, 0.0)

    result = target.eventFilter(viewport, event)

    assert result is False
    event.acceptProposedAction.assert_not_called()


def test_unhandled_event_type_returns_false(qapp):
    target, _viewer, viewport, _graph, _registry = _make_drop_target()
    event = _make_event(QEvent.Type.MouseMove, mime_match=True)

    result = target.eventFilter(viewport, event)

    assert result is False
