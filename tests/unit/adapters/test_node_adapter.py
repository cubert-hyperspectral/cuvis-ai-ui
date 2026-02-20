"""Tests for node adapter and node registry."""

from unittest.mock import Mock

from cuvis_ai_ui.adapters.node_adapter import (
    CuvisNodeAdapter,
    create_node_class,
    NodeRegistry,
    CATEGORY_COLORS,
    DEFAULT_NODE_COLOR,
)


def test_cuvis_node_adapter_init(qapp):
    """Test CuvisNodeAdapter initialization."""
    node = CuvisNodeAdapter()

    assert node._cuvis_class_path == ""
    assert node._cuvis_class_name == ""
    assert node._cuvis_source == "builtin"
    assert node._cuvis_plugin_name == ""
    assert node._cuvis_hparams == {}
    assert node._cuvis_execution_stages == {"always"}
    assert node._cuvis_input_specs == {}
    assert node._cuvis_output_specs == {}


def test_cuvis_node_adapter_properties(qapp):
    """Test CuvisNodeAdapter properties."""
    node = CuvisNodeAdapter()

    # Set internal values
    node._cuvis_class_path = "cuvis_ai.node.test.TestNode"
    node._cuvis_class_name = "TestNode"
    node._cuvis_source = "plugin"
    node._cuvis_plugin_name = "test_plugin"

    # Test property access
    assert node.cuvis_class_path == "cuvis_ai.node.test.TestNode"
    assert node.cuvis_class_name == "TestNode"
    assert node.cuvis_source == "plugin"
    assert node.cuvis_plugin_name == "test_plugin"


def test_cuvis_node_adapter_hparams_property(qapp):
    """Test CuvisNodeAdapter hparams property getter and setter."""
    node = CuvisNodeAdapter()

    # Set via property
    node.cuvis_hparams = {"param1": "value1", "param2": 42}

    # Get via property
    assert node.cuvis_hparams["param1"] == "value1"
    assert node.cuvis_hparams["param2"] == 42


def test_cuvis_node_adapter_execution_stages_property(qapp):
    """Test CuvisNodeAdapter execution_stages property."""
    node = CuvisNodeAdapter()

    # Default value
    assert node.cuvis_execution_stages == {"always"}

    # Set new value
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


def test_get_category_from_path(qapp):
    """Test category inference from class path."""
    node = CuvisNodeAdapter()

    # Test normalization category
    node._cuvis_class_path = "cuvis_ai.node.normalization.MinMaxNormalizer"
    assert node._get_category_from_path() == "normalization"

    # Test data category
    node._cuvis_class_path = "cuvis_ai.node.data.DataLoader"
    assert node._get_category_from_path() == "data"

    # Test model category
    node._cuvis_class_path = "cuvis_ai.node.model.ResNet"
    assert node._get_category_from_path() == "model"

    # Test utility category (default for unknown)
    node._cuvis_class_path = "cuvis_ai.node.unknown.UnknownNode"
    assert node._get_category_from_path() == "unknown"


def test_get_category_from_path_fallback(qapp):
    """Test category fallback for non-standard paths."""
    node = CuvisNodeAdapter()

    # Path without node keyword
    node._cuvis_class_path = "some.module.ClassName"
    category = node._get_category_from_path()
    assert category == "utility"  # Default fallback


def test_get_cuvis_config_basic(qapp):
    """Test exporting node configuration."""
    node = CuvisNodeAdapter()
    node._cuvis_class_path = "cuvis_ai.node.test.TestNode"
    node.set_name("test_node")

    config = node.get_cuvis_config()

    assert config["class_name"] == "cuvis_ai.node.test.TestNode"
    assert config["name"] == "test_node"
    assert "hparams" not in config  # Empty hparams not included


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
    node._cuvis_execution_stages = {"always"}  # Default value

    config = node.get_cuvis_config()

    assert "execution_stages" not in config  # Default not exported


def test_update_hparam(qapp):
    """Test updating a single hyperparameter."""
    node = CuvisNodeAdapter()

    node.update_hparam("param1", "value1")
    assert node._cuvis_hparams["param1"] == "value1"

    # Update existing
    node.update_hparam("param1", "new_value")
    assert node._cuvis_hparams["param1"] == "new_value"


def test_get_hparam(qapp):
    """Test getting hyperparameter values."""
    node = CuvisNodeAdapter()
    node._cuvis_hparams = {"param1": "value1", "param2": 42}

    # Get existing param
    assert node.get_hparam("param1") == "value1"
    assert node.get_hparam("param2") == 42

    # Get non-existing param with default
    assert node.get_hparam("nonexistent", "default") == "default"

    # Get non-existing param without default
    assert node.get_hparam("nonexistent") is None


def test_create_node_class(qapp, sample_node_info):
    """Test dynamically creating a node class."""
    node_class = create_node_class(sample_node_info)

    assert issubclass(node_class, CuvisNodeAdapter)
    assert node_class.NODE_NAME == "MinMaxNormalizer"
    assert "_" in node_class.__identifier__  # Path converted to underscores


def test_create_node_class_auto_configures(qapp):
    """Test that created node classes auto-configure on init."""
    node_info = {
        "class_name": "TestNode",
        "full_path": "cuvis_ai.node.test.TestNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
    }

    node_class = create_node_class(node_info)
    node = node_class()

    # Should auto-configure from node_info
    assert node._cuvis_class_name == "TestNode"
    assert node._cuvis_class_path == "cuvis_ai.node.test.TestNode"


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
    registry.register_node({"class_name": "Test"})  # Missing full_path

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
    info = node_registry.get_node_info("nonexistent.path")

    assert info is None


def test_node_registry_get_node_class(node_registry):
    """Test getting node class by class path."""
    node_class = node_registry.get_node_class("cuvis_ai.node.normalization.MinMaxNormalizer")

    assert node_class is not None
    assert issubclass(node_class, CuvisNodeAdapter)


def test_node_registry_get_node_class_not_found(node_registry):
    """Test getting non-existent node class returns None."""
    node_class = node_registry.get_node_class("nonexistent.path")

    assert node_class is None


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
    }

    plugin_node = {
        "class_name": "PluginNode",
        "full_path": "cuvis_ai_plugin.node.PluginNode",
        "source": "plugin",
        "plugin_name": "test_plugin",
        "input_specs": [],
        "output_specs": [],
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
    }

    plugin2_node = {
        "class_name": "Plugin2Node",
        "full_path": "plugin2.node.Plugin2Node",
        "source": "plugin",
        "plugin_name": "plugin2",
        "input_specs": [],
        "output_specs": [],
    }

    registry.register_nodes([plugin1_node, plugin2_node])

    plugin1_nodes = registry.get_nodes_by_plugin("plugin1")
    plugin2_nodes = registry.get_nodes_by_plugin("plugin2")

    assert len(plugin1_nodes) == 1
    assert plugin1_nodes[0]["class_name"] == "Plugin1Node"
    assert len(plugin2_nodes) == 1
    assert plugin2_nodes[0]["class_name"] == "Plugin2Node"


def test_node_registry_get_nodes_by_category():
    """Test grouping nodes by category."""
    registry = NodeRegistry()

    norm_node = {
        "class_name": "NormNode",
        "full_path": "cuvis_ai.node.normalization.NormNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
    }

    data_node = {
        "class_name": "DataNode",
        "full_path": "cuvis_ai.node.data.DataNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
    }

    registry.register_nodes([norm_node, data_node])

    categories = registry.get_nodes_by_category()

    assert "Normalization" in categories
    assert "Data" in categories
    assert len(categories["Normalization"]) == 1
    assert len(categories["Data"]) == 1


def test_node_registry_register_with_graph():
    """Test registering node classes with a graph."""
    registry = NodeRegistry()

    node_info = {
        "class_name": "TestNode",
        "full_path": "cuvis_ai.node.test.TestNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
    }

    registry.register_node(node_info)

    # Mock graph
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
        "full_path": "cuvis_ai.node.test.TestNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
    }

    registry.register_node(node_info)

    # Mock graph that raises exception on registration
    mock_graph = Mock()
    mock_graph.register_node = Mock(side_effect=Exception("Registration failed"))

    # Should not raise exception, just log and return 0
    count = registry.register_with_graph(mock_graph)

    assert count == 0


def test_node_registry_clear():
    """Test clearing the registry."""
    registry = NodeRegistry()

    node_info = {
        "class_name": "TestNode",
        "full_path": "cuvis_ai.node.test.TestNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
    }

    registry.register_node(node_info)
    assert len(registry) == 1

    registry.clear()
    assert len(registry) == 0
    assert registry._nodes == {}
    assert registry._node_classes == {}


def test_node_registry_contains(node_registry):
    """Test checking if node is registered."""
    assert "cuvis_ai.node.normalization.MinMaxNormalizer" in node_registry
    assert "nonexistent.path" not in node_registry


def test_category_colors_defined():
    """Test that category colors are properly defined."""
    assert isinstance(CATEGORY_COLORS, dict)
    assert len(CATEGORY_COLORS) > 0

    # Check some known categories
    assert "data" in CATEGORY_COLORS
    assert "normalization" in CATEGORY_COLORS
    assert "model" in CATEGORY_COLORS

    # Check color format (R, G, B, A)
    for color in CATEGORY_COLORS.values():
        assert len(color) == 4
        assert all(isinstance(c, int) for c in color)
        assert all(0 <= c <= 255 for c in color)


def test_default_node_color():
    """Test that default node color is defined."""
    assert isinstance(DEFAULT_NODE_COLOR, tuple)
    assert len(DEFAULT_NODE_COLOR) == 4
