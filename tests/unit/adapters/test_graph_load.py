"""Loading pipelines into a real NodeGraph.

These tests drive the serializer against NodeGraphQt itself, because the
failures they guard (an edge silently replaced on a single-connection input, a
node without ports, a stale registered node type) only show up in a real graph.
"""

import pytest
from NodeGraphQt import NodeGraph

from cuvis_ai_ui.adapters import NodeRegistry, PipelineSerializer
from cuvis_ai_ui.adapters.node_adapter import _parse_port_spec


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


def _config(nodes, connections, plugins=("p",)):
    return {
        "plugins": list(plugins),
        "nodes": [{"name": name, "class_name": cls, "hparams": {}} for name, cls in nodes],
        "connections": [{"source": s, "target": t} for s, t in connections],
    }


def _edges(graph):
    return {
        (node.name(), port.name(), other.node().name(), other.name())
        for node in graph.all_nodes()
        for port in node.output_ports()
        for other in port.connected_ports()
    }


@pytest.fixture
def graph(qapp):
    graph = NodeGraph()
    yield graph
    graph.clear_session()


def _load(graph, infos, config, known_plugins=None):
    registry = NodeRegistry()
    registry.register_nodes(infos)
    registry.register_with_graph(graph)
    serializer = PipelineSerializer(registry)
    serializer.known_plugins = known_plugins
    serializer.from_config(config, graph)
    return serializer


FAN_IN = [
    ("a", "p.Src"),
    ("b", "p.Src"),
    ("fuse", "p.Fuse"),
]
FAN_IN_EDGES = [
    ("a.outputs.out", "fuse.inputs.maps"),
    ("b.outputs.out", "fuse.inputs.maps"),
]


def test_parse_port_spec_keeps_variadic():
    _, spec = _parse_port_spec(_port("maps", variadic=True))
    assert spec.variadic is True


def test_fan_in_input_keeps_every_edge(graph):
    infos = [_info("p.Src", outputs=["out"]), _info("p.Fuse", inputs=["maps"], variadic=["maps"])]
    serializer = _load(graph, infos, _config(FAN_IN, FAN_IN_EDGES))
    assert _edges(graph) == {("a", "out", "fuse", "maps"), ("b", "out", "fuse", "maps")}
    assert serializer.last_missing_connections == []
    assert serializer.last_load_warnings == []


def test_edge_replaced_on_a_single_input_is_reported(graph):
    infos = [_info("p.Src", outputs=["out"]), _info("p.Fuse", inputs=["maps"])]
    serializer = _load(graph, infos, _config(FAN_IN, FAN_IN_EDGES))
    assert len(_edges(graph)) == 1
    assert serializer.last_missing_connections == ["a.outputs.out -> fuse.inputs.maps"]
    assert any("could not be drawn" in w for w in serializer.last_load_warnings)


def test_known_class_without_ports_takes_them_from_connections(graph):
    infos = [_info("p.Src", outputs=["out"]), _info("p.Bare"), _info("p.Sink", inputs=["mask"])]
    config = _config(
        [("src", "p.Src"), ("bare", "p.Bare"), ("sink", "p.Sink")],
        [("src.outputs.out", "bare.inputs.cube"), ("bare.outputs.mask", "sink.inputs.mask")],
    )
    serializer = _load(graph, infos, config)
    assert _edges(graph) == {("src", "out", "bare", "cube"), ("bare", "mask", "sink", "mask")}
    assert serializer.last_missing_connections == []
    assert any(
        "Ports taken from connections" in w and "Bare" in w for w in serializer.last_load_warnings
    )


def test_two_spec_less_instances_each_keep_only_their_own_ports(graph):
    infos = [
        _info("p.Src", outputs=["out"]),
        _info("p.Bare"),
        _info("p.Sink", inputs=["mask"]),
    ]
    config = _config(
        [
            ("src1", "p.Src"),
            ("bare1", "p.Bare"),
            ("sink1", "p.Sink"),
            ("src2", "p.Src"),
            ("bare2", "p.Bare"),
            ("sink2", "p.Sink"),
        ],
        [
            ("src1.outputs.out", "bare1.inputs.cube"),
            ("bare1.outputs.mask", "sink1.inputs.mask"),
            ("src2.outputs.out", "bare2.inputs.alpha"),
            ("bare2.outputs.beta", "sink2.inputs.mask"),
        ],
    )
    serializer = _load(graph, infos, config)

    assert _edges(graph) == {
        ("src1", "out", "bare1", "cube"),
        ("bare1", "mask", "sink1", "mask"),
        ("src2", "out", "bare2", "alpha"),
        ("bare2", "beta", "sink2", "mask"),
    }
    assert serializer.last_missing_connections == []

    nodes_by_name = {node.name(): node for node in graph.all_nodes()}
    bare1 = nodes_by_name["bare1"]
    bare2 = nodes_by_name["bare2"]
    assert set(bare1.inputs()) == {"cube"}
    assert set(bare1.outputs()) == {"mask"}
    assert set(bare2.inputs()) == {"alpha"}
    assert set(bare2.outputs()) == {"beta"}


def test_class_path_resolved_by_last_segment_round_trips(graph):
    """A pipeline naming a class by its defining module, while the registry
    holds the package export, loads as a real node (not a placeholder) and
    saves back with the YAML's original class_name."""
    infos = [_info("p_pkg.node.Cls", inputs=["cube"], outputs=["mask"])]
    config = _config(
        [("n", "p_pkg.node.module.Cls")],
        [],
    )
    serializer = _load(graph, infos, config)

    assert serializer._load_missing_nodes == set()
    assert not any("Missing node classes" in w for w in serializer.last_load_warnings)

    node = next(iter(graph.all_nodes()))
    assert set(node.inputs()) == {"cube"}
    assert set(node.outputs()) == {"mask"}

    saved = serializer.to_config(graph)
    assert saved["nodes"][0]["class_name"] == "p_pkg.node.module.Cls"
    assert saved["plugins"] == ["p"]


def test_placeholder_fan_in_keeps_every_edge(graph):
    infos = [_info("p.Src", outputs=["out"])]
    serializer = _load(graph, infos, _config(FAN_IN, FAN_IN_EDGES))
    assert len(_edges(graph)) == 2
    assert serializer.last_missing_connections == []


def test_unknown_plugin_names_are_reported(graph):
    infos = [_info("p.Src", outputs=["out"])]
    config = _config([("a", "p.Src")], [], plugins=("p", "nope"))
    serializer = _load(graph, infos, config, known_plugins={"p"})
    assert any("Plugins not available: nope" in w for w in serializer.last_load_warnings)


def test_plugin_check_is_skipped_without_known_plugins(graph):
    infos = [_info("p.Src", outputs=["out"])]
    config = _config([("a", "p.Src")], [], plugins=("p", "nope"))
    serializer = _load(graph, infos, config, known_plugins=None)
    assert serializer.last_load_warnings == []


def test_to_config_keeps_plugin_of_node_the_registry_no_longer_knows(graph):
    """A folder switch clears the shared registry before the kept pipeline is
    saved; the node's own stored plugin name still attributes it correctly."""
    infos = [_info("p.Src", outputs=["out"])]
    config = _config([("a", "p.Src")], [])
    serializer = _load(graph, infos, config)

    # Simulate the registry losing the plugin's classes, as a folder switch does.
    serializer.node_registry.clear()

    saved = serializer.to_config(graph)
    assert saved["plugins"] == ["p"]


def test_to_config_keeps_declared_plugin_for_a_placeholder_node(graph):
    """A pipeline that declares a plugin whose class is unknown at load time
    (a placeholder) keeps that plugin in a later save, even though no node
    can be attributed to it."""
    config = _config([("ghost", "missing.pkg.Ghost")], [], plugins=("q",))
    serializer = _load(graph, [], config)

    saved = serializer.to_config(graph)
    assert saved["plugins"] == ["q"]


def test_to_config_drops_a_declared_plugin_with_no_remaining_node(graph):
    """A pipeline whose nodes are all attributable lists only the derived
    plugins; a declared plugin with no node left in the graph is dropped,
    same as before this node-owner tracking was added."""
    infos = [_info("p.Src", outputs=["out"])]
    config = _config([("a", "p.Src")], [], plugins=("p", "q"))
    serializer = _load(graph, infos, config)

    saved = serializer.to_config(graph)
    assert saved["plugins"] == ["p"]


def test_register_with_graph_replaces_a_changed_node_type(graph):
    registry = NodeRegistry()
    registry.register_nodes([_info("p.Node", inputs=["old"])])
    registry.register_with_graph(graph)

    registry.clear()
    registry.register_nodes([_info("p.Node", inputs=["new"])])
    registry.register_with_graph(graph)

    node = graph.create_node(registry.get_node_class("p.Node").type_)
    assert list(node.inputs()) == ["new"]


def test_register_with_graph_drops_node_types_of_removed_plugins(graph):
    """A plugin that is gone from the catalog (folder switch, disabled in the
    Plugin Manager) must not stay creatable through the canvas's Tab search."""
    registry = NodeRegistry()
    registry.register_nodes(
        [_info("p.Keep", inputs=["x"]), _info("q.Gone", inputs=["x"], plugin="q")]
    )
    registry.register_with_graph(graph)
    gone_type = registry.get_node_class("q.Gone").type_
    assert gone_type in graph.registered_nodes()

    registry.clear()
    registry.register_nodes([_info("p.Keep", inputs=["x"])])
    registry.register_with_graph(graph)

    registered = graph.registered_nodes()
    assert gone_type not in registered
    assert registry.get_node_class("p.Keep").type_ in registered
    assert all(graph.node_factory.names.values())


def test_register_with_graph_keeps_placeholder_node_types(graph):
    """Placeholder types the serializer registered for unknown classes are not
    the registry's to remove."""
    config = _config([("ghost", "missing.pkg.Ghost")], [], plugins=("q",))
    serializer = _load(graph, [_info("p.Src", outputs=["out"])], config)
    before = set(graph.registered_nodes())

    serializer.node_registry.register_with_graph(graph)

    assert before <= set(graph.registered_nodes())


def test_class_of_a_missing_plugin_is_not_borrowed_from_another_plugin(graph):
    """A node whose own plugin is missing loads as a placeholder instead of
    resolving to another plugin's class of the same name, and saving keeps the
    pipeline's declared plugins instead of rewriting them to that plugin."""
    infos = [_info("other_pkg.node.Transform", inputs=["x"], plugin="other")]
    config = _config([("n", "wanted_pkg.node.Transform")], [], plugins=("wanted",))
    serializer = _load(graph, infos, config, known_plugins={"wanted", "other"})

    assert serializer._load_missing_nodes == {"wanted_pkg.node.Transform"}

    saved = serializer.to_config(graph)
    assert saved["nodes"][0]["class_name"] == "wanted_pkg.node.Transform"
    assert saved["plugins"] == ["wanted"]


def test_from_config_failed_validation_keeps_the_open_pipelines_plugins(graph):
    """A load that fails Pydantic validation must not wipe the plugins the
    graph still on screen needs: to_config has to keep declaring them."""
    config = _config([("ghost", "missing.pkg.Ghost")], [], plugins=("q",))
    serializer = _load(graph, [], config)
    assert serializer.to_config(graph)["plugins"] == ["q"]

    with pytest.raises(ValueError):
        serializer.from_config({"nodes": [{"name": "bad"}]}, graph)

    saved = serializer.to_config(graph)
    assert saved["plugins"] == ["q"]


def test_to_config_prefers_the_nodes_stored_owner_over_the_registry(graph):
    """A folder switch can replace the registry's classes with a different
    plugin's class of the same bare name; the node's own stored owner from
    when it was created must still win over whatever the registry resolves
    the class_name to now."""
    infos = [_info("a.PrivateNode", inputs=["x"], plugin="A")]
    config = _config([("n", "a.PrivateNode")], [])
    serializer = _load(graph, infos, config)

    # Simulate a folder switch: the registry is cleared and re-registered with
    # a different plugin's class that resolves to the same bare name.
    serializer.node_registry.clear()
    serializer.node_registry.register_nodes([_info("b.PrivateNode", inputs=["x"], plugin="B")])

    saved = serializer.to_config(graph)
    assert saved["plugins"] == ["A"]


def test_to_config_core_builtin_needs_no_plugin(graph):
    """A core built-in carries an empty plugin_name: it needs no declaration and
    is not reported as a node whose owner is unknown."""
    infos = [_info("p.Src", outputs=["out"]), _info("core.Builtin", inputs=["x"], plugin="")]
    config = _config([("a", "p.Src"), ("b", "core.Builtin")], [("a.outputs.out", "b.inputs.x")])
    serializer = _load(graph, infos, config)

    saved = serializer.to_config(graph)

    assert saved["plugins"] == ["p"]
    assert not any("owning plugin" in w for w in serializer.last_load_warnings)
