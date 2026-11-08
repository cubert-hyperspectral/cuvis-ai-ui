"""Node catalog entries and a real NodeGraph for the adapter tests."""

import pytest
from NodeGraphQt import NodeGraph


def _port(name, variadic=False):
    return {
        "name": name,
        "dtype": "float32",
        "shape": "any",
        "optional": False,
        "description": "",
        "variadic": variadic,
    }


def _info(path, inputs=(), outputs=(), variadic=(), plugin="p"):
    return {
        "class_name": path.rsplit(".", 1)[-1],
        "full_path": path,
        "source": "plugin",
        "plugin_name": plugin,
        "input_specs": [_port(n, n in variadic) for n in inputs],
        "output_specs": [_port(n) for n in outputs],
        "category": 0,
        "tags": [],
        "icon_svg": b"",
    }


@pytest.fixture
def graph(qapp):
    graph = NodeGraph()
    yield graph
    graph.clear_session()
