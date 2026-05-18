"""Tests for node adapter and node registry."""

from unittest.mock import Mock

import pytest

from cuvis_ai_schemas.enums import NodeCategory, NodeTag
from cuvis_ai_schemas.extensions.ui.node_display import CATEGORY_STYLES, TAG_STYLES
from cuvis_ai_schemas.grpc.conversions import (
    node_category_to_proto,
    node_tag_to_proto,
)
from cuvis_ai_schemas.pipeline.ports import PortSpec

from cuvis_ai_ui.adapters.node_adapter import (
    CuvisNodeAdapter,
    DEFAULT_NODE_COLOR,
    NodeRegistry,
    _parse_port_spec,
    _parse_shape,
    category_color,
    create_node_class,
    tag_chip_color,
)


def test_cuvis_node_adapter_init(qapp):
    """Test CuvisNodeAdapter initialization including new metadata attrs."""
    node = CuvisNodeAdapter()

    assert node._cuvis_class_path == ""
    assert node._cuvis_class_name == ""
    assert node._cuvis_source == "builtin"
    assert node._cuvis_plugin_name == ""
    assert node._cuvis_hparams == {}
    assert node._cuvis_execution_stages == {"always"}
    assert node._cuvis_input_specs == {}
    assert node._cuvis_output_specs == {}
    assert node._cuvis_category == NodeCategory.UNSPECIFIED
    assert node._cuvis_tags == []
    assert node._cuvis_icon_svg == b""


def test_cuvis_node_adapter_properties(qapp):
    """Test CuvisNodeAdapter properties."""
    node = CuvisNodeAdapter()

    node._cuvis_class_path = "cuvis_ai.node.test.TestNode"
    node._cuvis_class_name = "TestNode"
    node._cuvis_source = "plugin"
    node._cuvis_plugin_name = "test_plugin"

    assert node.cuvis_class_path == "cuvis_ai.node.test.TestNode"
    assert node.cuvis_class_name == "TestNode"
    assert node.cuvis_source == "plugin"
    assert node.cuvis_plugin_name == "test_plugin"


def test_cuvis_node_adapter_hparams_property(qapp):
    """Test CuvisNodeAdapter hparams property getter and setter."""
    node = CuvisNodeAdapter()

    node.cuvis_hparams = {"param1": "value1", "param2": 42}

    assert node.cuvis_hparams["param1"] == "value1"
    assert node.cuvis_hparams["param2"] == 42


def test_cuvis_node_adapter_execution_stages_property(qapp):
    """Test CuvisNodeAdapter execution_stages property."""
    node = CuvisNodeAdapter()

    assert node.cuvis_execution_stages == {"always"}

    node.cuvis_execution_stages = {"train", "inference"}
    assert node.cuvis_execution_stages == {"train", "inference"}


def test_configure_from_node_info(qapp, sample_node_info):
    """Test configuring node from node info dictionary."""
    node = CuvisNodeAdapter()
    node.configure_from_node_info(sample_node_info)

    assert node._cuvis_class_name == "MinMaxNormalizer"
    assert node._cuvis_class_path == "cuvis_ai.node.normalization.MinMaxNormalizer"
    assert node._cuvis_source == "builtin"
    assert len(node._cuvis_input_specs) == 1
    assert len(node._cuvis_output_specs) == 1
    assert node._cuvis_category == NodeCategory.TRANSFORM
    assert node._cuvis_icon_svg == b""


def test_cuvis_category_returns_correct_enum(qapp):
    """cuvis_category property resolves wire int to the correct NodeCategory."""
    node = CuvisNodeAdapter()
    info = {
        "class_name": "HsiLoader",
        "full_path": "cuvis_ai.node.data.HsiLoader",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": node_category_to_proto(NodeCategory.SOURCE),
        "tags": [],
        "icon_svg": b"",
    }
    node.configure_from_node_info(info)

    assert node.cuvis_category == NodeCategory.SOURCE


def test_cuvis_tags_narrows_known_ints_drops_unknown(qapp):
    """cuvis_tags narrows known wire ints to NodeTag; unknown ints are dropped silently."""
    node = CuvisNodeAdapter()
    hsi_wire = node_tag_to_proto(NodeTag.HYPERSPECTRAL)
    info = {
        "class_name": "T",
        "full_path": "a.b.T",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [hsi_wire, 99999],  # 99999 is not a known tag
        "icon_svg": b"",
    }
    node.configure_from_node_info(info)

    tags = node.cuvis_tags
    assert NodeTag.HYPERSPECTRAL in tags
    assert len(tags) == 1  # 99999 dropped


def test_cuvis_icon_svg_passthrough(qapp):
    """cuvis_icon_svg returns the exact bytes from node_info."""
    node = CuvisNodeAdapter()
    info = {
        "class_name": "T",
        "full_path": "a.b.T",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [],
        "icon_svg": b"<svg/>",
    }
    node.configure_from_node_info(info)

    assert node.cuvis_icon_svg == b"<svg/>"


def test_category_color_matches_category_styles():
    """category_color() RGB must match the hex parse of CATEGORY_STYLES[cat]['border']."""
    for cat in NodeCategory:
        r, g, b, a = category_color(cat)
        styles = CATEGORY_STYLES.get(cat, CATEGORY_STYLES[NodeCategory.UNSPECIFIED])
        h = styles["border"]
        assert r == int(h[1:3], 16), f"{cat}: red mismatch"
        assert g == int(h[3:5], 16), f"{cat}: green mismatch"
        assert b == int(h[5:7], 16), f"{cat}: blue mismatch"
        assert a == 255


def test_tag_chip_color_matches_tag_styles():
    """tag_chip_color() RGB must match TAG_STYLES[tag]['badge_color'] for known tags."""
    spot_check = [NodeTag.HYPERSPECTRAL, NodeTag.SEGMENTATION, NodeTag.TORCH]
    for tag in spot_check:
        r, g, b, a = tag_chip_color(tag)
        h = TAG_STYLES[tag]["badge_color"]
        assert r == int(h[1:3], 16), f"{tag}: red mismatch"
        assert g == int(h[3:5], 16), f"{tag}: green mismatch"
        assert b == int(h[5:7], 16), f"{tag}: blue mismatch"
        assert a == 200


def test_default_node_color():
    """Test that DEFAULT_NODE_COLOR is defined and is a valid RGBA tuple."""
    assert isinstance(DEFAULT_NODE_COLOR, tuple)
    assert len(DEFAULT_NODE_COLOR) == 4
    assert all(0 <= c <= 255 for c in DEFAULT_NODE_COLOR)


def test_get_cuvis_config_basic(qapp):
    """Test exporting node configuration."""
    node = CuvisNodeAdapter()
    node._cuvis_class_path = "cuvis_ai.node.test.TestNode"
    node.set_name("test_node")

    config = node.get_cuvis_config()

    assert config["class_name"] == "cuvis_ai.node.test.TestNode"
    assert config["name"] == "test_node"
    assert "hparams" not in config


def test_get_cuvis_config_with_hparams(qapp):
    """Test exporting node configuration with hyperparameters."""
    node = CuvisNodeAdapter()
    node._cuvis_class_path = "cuvis_ai.node.test.TestNode"
    node.set_name("test_node")
    node._cuvis_hparams = {"param1": "value1", "param2": 42}

    config = node.get_cuvis_config()

    assert config["hparams"]["param1"] == "value1"
    assert config["hparams"]["param2"] == 42


def test_get_cuvis_config_with_execution_stages(qapp):
    """Test exporting node configuration with custom execution stages."""
    node = CuvisNodeAdapter()
    node._cuvis_class_path = "cuvis_ai.node.test.TestNode"
    node.set_name("test_node")
    node._cuvis_execution_stages = {"train", "inference"}

    config = node.get_cuvis_config()

    assert "execution_stages" in config
    assert set(config["execution_stages"]) == {"train", "inference"}


def test_get_cuvis_config_default_execution_stages(qapp):
    """Test that default execution stages are not included in config."""
    node = CuvisNodeAdapter()
    node._cuvis_class_path = "cuvis_ai.node.test.TestNode"
    node.set_name("test_node")
    node._cuvis_execution_stages = {"always"}

    config = node.get_cuvis_config()

    assert "execution_stages" not in config


def test_update_hparam(qapp):
    """Test updating a single hyperparameter."""
    node = CuvisNodeAdapter()

    node.update_hparam("param1", "value1")
    assert node._cuvis_hparams["param1"] == "value1"

    node.update_hparam("param1", "new_value")
    assert node._cuvis_hparams["param1"] == "new_value"


def test_get_hparam(qapp):
    """Test getting hyperparameter values."""
    node = CuvisNodeAdapter()
    node._cuvis_hparams = {"param1": "value1", "param2": 42}

    assert node.get_hparam("param1") == "value1"
    assert node.get_hparam("param2") == 42
    assert node.get_hparam("nonexistent", "default") == "default"
    assert node.get_hparam("nonexistent") is None


def test_create_node_class(qapp, sample_node_info):
    """Test dynamically creating a node class."""
    node_class = create_node_class(sample_node_info)

    assert issubclass(node_class, CuvisNodeAdapter)
    assert node_class.NODE_NAME == "MinMaxNormalizer"
    assert "_" in node_class.__identifier__


def test_create_node_class_auto_configures(qapp):
    """Test that created node classes auto-configure on init."""
    node_info = {
        "class_name": "TestNode",
        "full_path": "cuvis_ai.node.test.TestNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": node_category_to_proto(NodeCategory.TRANSFORM),
        "tags": [],
        "icon_svg": b"",
    }

    node_class = create_node_class(node_info)
    node = node_class()

    assert node._cuvis_class_name == "TestNode"
    assert node._cuvis_class_path == "cuvis_ai.node.test.TestNode"
    assert node._cuvis_category == NodeCategory.TRANSFORM


def test_node_registry_init():
    """Test NodeRegistry initialization."""
    registry = NodeRegistry()

    assert registry._nodes == {}
    assert registry._node_classes == {}
    assert len(registry) == 0


def test_node_registry_register_node(sample_node_info):
    """Test registering a single node."""
    registry = NodeRegistry()
    registry.register_node(sample_node_info)

    assert len(registry) == 1
    assert "cuvis_ai.node.normalization.MinMaxNormalizer" in registry


def test_node_registry_register_node_without_path():
    """Test registering node without full_path is skipped."""
    registry = NodeRegistry()
    registry.register_node({"class_name": "Test"})

    assert len(registry) == 0


def test_node_registry_register_nodes(sample_node_info):
    """Test registering multiple nodes."""
    registry = NodeRegistry()

    node_info_2 = {
        "class_name": "DataLoader",
        "full_path": "cuvis_ai.node.data.DataLoader",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": node_category_to_proto(NodeCategory.SOURCE),
        "tags": [],
        "icon_svg": b"",
    }

    registry.register_nodes([sample_node_info, node_info_2])

    assert len(registry) == 2
    assert "cuvis_ai.node.normalization.MinMaxNormalizer" in registry
    assert "cuvis_ai.node.data.DataLoader" in registry


def test_node_registry_get_node_info(node_registry):
    """Test getting node info by class path."""
    info = node_registry.get_node_info("cuvis_ai.node.normalization.MinMaxNormalizer")

    assert info is not None
    assert info["class_name"] == "MinMaxNormalizer"


def test_node_registry_get_node_info_not_found(node_registry):
    """Test getting non-existent node info returns None."""
    assert node_registry.get_node_info("nonexistent.path") is None


def test_node_registry_get_node_class(node_registry):
    """Test getting node class by class path."""
    node_class = node_registry.get_node_class("cuvis_ai.node.normalization.MinMaxNormalizer")

    assert node_class is not None
    assert issubclass(node_class, CuvisNodeAdapter)


def test_node_registry_get_node_class_not_found(node_registry):
    """Test getting non-existent node class returns None."""
    assert node_registry.get_node_class("nonexistent.path") is None


def test_node_registry_get_all_nodes(node_registry):
    """Test getting all registered nodes."""
    all_nodes = node_registry.get_all_nodes()

    assert len(all_nodes) == 1
    assert all_nodes[0]["class_name"] == "MinMaxNormalizer"


def test_node_registry_get_nodes_by_source():
    """Test filtering nodes by source."""
    registry = NodeRegistry()

    builtin_node = {
        "class_name": "BuiltinNode",
        "full_path": "cuvis_ai.node.builtin.BuiltinNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [],
        "icon_svg": b"",
    }

    plugin_node = {
        "class_name": "PluginNode",
        "full_path": "cuvis_ai_plugin.node.PluginNode",
        "source": "plugin",
        "plugin_name": "test_plugin",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [],
        "icon_svg": b"",
    }

    registry.register_nodes([builtin_node, plugin_node])

    builtin_nodes = registry.get_nodes_by_source("builtin")
    plugin_nodes = registry.get_nodes_by_source("plugin")

    assert len(builtin_nodes) == 1
    assert builtin_nodes[0]["class_name"] == "BuiltinNode"
    assert len(plugin_nodes) == 1
    assert plugin_nodes[0]["class_name"] == "PluginNode"


def test_node_registry_get_nodes_by_plugin():
    """Test filtering nodes by plugin name."""
    registry = NodeRegistry()

    plugin1_node = {
        "class_name": "Plugin1Node",
        "full_path": "plugin1.node.Plugin1Node",
        "source": "plugin",
        "plugin_name": "plugin1",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [],
        "icon_svg": b"",
    }

    plugin2_node = {
        "class_name": "Plugin2Node",
        "full_path": "plugin2.node.Plugin2Node",
        "source": "plugin",
        "plugin_name": "plugin2",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [],
        "icon_svg": b"",
    }

    registry.register_nodes([plugin1_node, plugin2_node])

    plugin1_nodes = registry.get_nodes_by_plugin("plugin1")
    plugin2_nodes = registry.get_nodes_by_plugin("plugin2")

    assert len(plugin1_nodes) == 1
    assert plugin1_nodes[0]["class_name"] == "Plugin1Node"
    assert len(plugin2_nodes) == 1
    assert plugin2_nodes[0]["class_name"] == "Plugin2Node"


def test_group_by_category_basic():
    """group_by_category groups nodes by their NodeCategory enum key."""
    registry = NodeRegistry()

    transform_node = {
        "class_name": "NormNode",
        "full_path": "cuvis_ai.node.normalization.NormNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": node_category_to_proto(NodeCategory.TRANSFORM),
        "tags": [],
        "icon_svg": b"",
    }

    source_node = {
        "class_name": "DataNode",
        "full_path": "cuvis_ai.node.data.DataNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": node_category_to_proto(NodeCategory.SOURCE),
        "tags": [],
        "icon_svg": b"",
    }

    registry.register_nodes([transform_node, source_node])
    grouped = registry.group_by_category()

    assert NodeCategory.TRANSFORM in grouped
    assert NodeCategory.SOURCE in grouped
    assert len(grouped[NodeCategory.TRANSFORM]) == 1
    assert len(grouped[NodeCategory.SOURCE]) == 1


def test_group_by_category_absent_when_empty():
    """Categories with no nodes must be absent from the result dict."""
    registry = NodeRegistry()

    node = {
        "class_name": "T",
        "full_path": "a.b.T",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": node_category_to_proto(NodeCategory.TRANSFORM),
        "tags": [],
        "icon_svg": b"",
    }
    registry.register_node(node)

    grouped = registry.group_by_category()

    assert NodeCategory.SINK not in grouped


def test_group_by_category_accepts_subset():
    """group_by_category can be given an explicit node list subset."""
    registry = NodeRegistry()

    n1 = {
        "class_name": "A",
        "full_path": "a.A",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": node_category_to_proto(NodeCategory.SOURCE),
        "tags": [],
        "icon_svg": b"",
    }
    n2 = {
        "class_name": "B",
        "full_path": "a.B",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": node_category_to_proto(NodeCategory.SINK),
        "tags": [],
        "icon_svg": b"",
    }
    registry.register_nodes([n1, n2])

    # Pass only n1 — n2 must not appear
    grouped = registry.group_by_category([n1])

    assert NodeCategory.SOURCE in grouped
    assert NodeCategory.SINK not in grouped


def test_node_registry_register_with_graph():
    """Test registering node classes with a graph."""
    registry = NodeRegistry()

    node_info = {
        "class_name": "TestNode",
        "full_path": "cuvis_ai.node.test.TestNode2",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [],
        "icon_svg": b"",
    }

    registry.register_node(node_info)

    mock_graph = Mock()
    mock_graph.register_node = Mock()

    count = registry.register_with_graph(mock_graph)

    assert count == 1
    mock_graph.register_node.assert_called_once()


def test_node_registry_register_with_graph_handles_errors():
    """Test that register_with_graph handles registration errors gracefully."""
    registry = NodeRegistry()

    node_info = {
        "class_name": "TestNode",
        "full_path": "cuvis_ai.node.test.TestNode3",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [],
        "icon_svg": b"",
    }

    registry.register_node(node_info)

    mock_graph = Mock()
    mock_graph.register_node = Mock(side_effect=Exception("Registration failed"))

    count = registry.register_with_graph(mock_graph)

    assert count == 0


def test_node_registry_clear():
    """Test clearing the registry."""
    registry = NodeRegistry()

    registry.register_node(
        {
            "class_name": "TestNode",
            "full_path": "cuvis_ai.node.test.TestNode4",
            "source": "builtin",
            "input_specs": [],
            "output_specs": [],
            "category": 0,
            "tags": [],
            "icon_svg": b"",
        }
    )
    assert len(registry) == 1

    registry.clear()
    assert len(registry) == 0
    assert registry._nodes == {}
    assert registry._node_classes == {}


def test_node_registry_contains(node_registry):
    """Test checking if node is registered."""
    assert "cuvis_ai.node.normalization.MinMaxNormalizer" in node_registry
    assert "nonexistent.path" not in node_registry


@pytest.mark.parametrize(
    "shape_in, expected",
    [
        ([3, 224, 224], (3, 224, 224)),
        ("[-1, -1]", (-1, -1)),
        ((1, 2, 3), (1, 2, 3)),
        ([], ()),
        # _parse_shape uses ``object`` typing so it can absorb unexpected runtime
        # values like None and fall through to the empty-tuple default; this
        # pins the runtime contract independent of the typing contract.
        (None, ()),
        ("[1, b, -1]", (1, "b", -1)),
    ],
)
def test_parse_shape_handles_list_str_tuple_and_unexpected(shape_in, expected):
    assert _parse_shape(shape_in) == expected


def test_parse_port_spec_dict_with_list_shape():
    name, spec = _parse_port_spec(
        {"name": "x", "dtype": "float32", "shape": [3, 224, 224], "optional": False}
    )
    assert name == "x"
    assert spec.dtype == "float32"
    assert spec.shape == (3, 224, 224)
    assert spec.optional is False


def test_parse_port_spec_dict_with_string_shape():
    name, spec = _parse_port_spec({"name": "y", "shape": "[-1, -1]"})
    assert name == "y"
    assert spec.shape == (-1, -1)


def test_parse_port_spec_dict_with_tuple_shape():
    name, spec = _parse_port_spec({"name": "z", "shape": (1, 2)})
    assert name == "z"
    assert spec.shape == (1, 2)


def test_parse_port_spec_passes_raw_portspec_through():
    raw = PortSpec(dtype="any", shape=(), description="d", optional=True)
    name, spec = _parse_port_spec(raw)
    assert name == "unknown"
    assert spec is raw  # identity: the existing PortSpec is reused, not rebuilt


def test_parse_port_spec_dict_missing_optional_fields():
    name, spec = _parse_port_spec({})
    assert name == "unknown"
    assert spec.dtype == "any"
    assert spec.shape == ()
    assert spec.description == ""
    assert spec.optional is False


def test_node_class_init_uses_class_attribute_node_info(qapp):
    """The dynamic ``__init__`` reads ``self.__class__._node_info`` rather than
    closing over the dict captured at class creation. This test pins that
    contract: replacing the class attribute with a fresh dict before the next
    instantiation must change what ``configure_from_node_info`` sees.
    """
    info_a = {
        "class_name": "A",
        "full_path": "x.A",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [],
        "icon_svg": b"",
    }
    cls = create_node_class(info_a)

    instance_a = cls()
    assert instance_a.cuvis_class_name == "A"

    # Replace the class attribute entirely with a fresh dict (not in-place
    # mutation, which a closure over info_a would also see). A closure-captured
    # __init__ would still configure from info_a here; the class-attr __init__
    # picks up info_b.
    info_b = {
        "class_name": "B",
        "full_path": "x.B",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [],
        "icon_svg": b"",
    }
    cls._node_info = info_b
    instance_b = cls()

    assert instance_b.cuvis_class_name == "B"
    assert instance_b.cuvis_class_path == "x.B"
