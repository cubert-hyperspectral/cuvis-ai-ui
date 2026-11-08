"""The canvas shows each node's pipeline name with its class on a second line.

Driven against a real NodeGraph, since the label layout lives in the
NodeGraphQt item.
"""

import pytest
from NodeGraphQt import NodeGraph
from NodeGraphQt.constants import LayoutDirectionEnum

from cuvis_ai_ui.adapters import NodeRegistry, PipelineSerializer


def _info(path, inputs=("frame_id",), outputs=("mask",)):
    def port(name):
        return {"name": name, "dtype": "float32", "shape": "any", "optional": False}

    return {
        "class_name": path.rsplit(".", 1)[-1],
        "full_path": path,
        "source": "plugin",
        "plugin_name": "p",
        "input_specs": [port(n) for n in inputs],
        "output_specs": [port(n) for n in outputs],
        "category": 0,
        "tags": [],
        "icon_svg": b"",
    }


@pytest.fixture
def graph(qapp):
    graph = NodeGraph()
    yield graph
    graph.clear_session()


def _load_one(graph, name, class_path, infos=()):
    registry = NodeRegistry()
    registry.register_nodes(list(infos))
    registry.register_with_graph(graph)
    PipelineSerializer(registry).from_config(
        {
            "plugins": ["p"],
            "nodes": [{"name": name, "class_name": class_path, "hparams": {}}],
            "connections": [],
        },
        graph,
    )
    (node,) = graph.all_nodes()
    return node


def _bottom(item):
    return item.pos().y() + item.boundingRect().height()


def test_a_loaded_node_shows_its_name_over_its_class(graph):
    path = "p.TrackingResultsReader"
    node = _load_one(graph, "gt_reader", path, [_info(path)])
    view = node.view

    assert view.text_item.toPlainText() == "gt_reader"
    assert view.class_item.toPlainText() == "TrackingResultsReader"
    assert view.class_item.isVisible()
    assert view.class_item.pos().y() >= _bottom(view.text_item) - 1.0
    first_port_y = min(port.pos().y() for port in [*view.inputs, *view.outputs])
    assert _bottom(view.class_item) <= first_port_y + 1.0


def test_the_class_line_is_smaller_than_the_name(graph):
    path = "p.TrackingResultsReader"
    view = _load_one(graph, "gt_reader", path, [_info(path)]).view

    assert view.class_item.font().pointSizeF() < view.text_item.font().pointSizeF()


def test_a_long_class_fits_inside_the_node(graph):
    path = "p.TrackingPointerOverlayNodeWithAVeryLongClassName"
    view = _load_one(graph, "a", path, [_info(path, inputs=(), outputs=("x",))]).view

    assert view.class_item.boundingRect().width() <= view.width


def test_a_placeholder_shows_the_class_from_its_path(graph):
    view = _load_one(graph, "gt_pointer", "p.TrackingPointerOverlayNode").view

    assert view.text_item.toPlainText() == "gt_pointer"
    assert view.class_item.toPlainText() == "TrackingPointerOverlayNode"


def test_renaming_a_node_keeps_its_class_line(graph):
    path = "p.Src"
    node = _load_one(graph, "a", path, [_info(path)])

    node.set_name("source")

    assert node.view.text_item.toPlainText() == "source"
    assert node.view.class_item.toPlainText() == "Src"


def test_the_vertical_layout_hides_the_class_line_until_horizontal_again(graph):
    path = "p.Src"
    view = _load_one(graph, "a", path, [_info(path)]).view
    horizontal = (view.class_item.pos().y(), [port.pos().y() for port in view.inputs])

    view.layout_direction = LayoutDirectionEnum.VERTICAL.value
    assert not view.class_item.isVisible()

    view.layout_direction = LayoutDirectionEnum.HORIZONTAL.value
    assert view.class_item.isVisible()
    assert (view.class_item.pos().y(), [port.pos().y() for port in view.inputs]) == horizontal


def test_zoomed_out_proxy_mode_hides_the_class_line(graph):
    path = "p.Src"
    view = _load_one(graph, "a", path, [_info(path)]).view

    view.set_proxy_mode(True)
    assert not view.class_item.isVisible()
    view.set_proxy_mode(False)
    assert view.class_item.isVisible()
