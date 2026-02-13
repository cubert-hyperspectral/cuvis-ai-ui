"""Tests for pipeline serializer (YAML ↔ NodeGraphQt conversion)."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from NodeGraphQt import NodeGraph

from cuvis_ai_ui.adapters.pipeline_serializer import PipelineSerializer
from cuvis_ai_ui.adapters import CuvisNodeAdapter


@pytest.fixture
def mock_graph():
    """Mock NodeGraph for testing."""
    graph = Mock(spec=NodeGraph)
    graph.clear_session = Mock()
    graph.all_nodes = Mock(return_value=[])
    graph.registered_nodes = Mock(return_value=[])
    graph.register_node = Mock()
    graph.create_node = Mock()
    return graph


@pytest.fixture
def pipeline_serializer(node_registry):
    """PipelineSerializer with test node registry."""
    return PipelineSerializer(node_registry)


def test_pipeline_serializer_init(node_registry):
    """Test PipelineSerializer initialization."""
    serializer = PipelineSerializer(node_registry)

    assert serializer.node_registry == node_registry
    assert serializer.last_load_warnings == []
    assert serializer._load_missing_nodes == set()
    assert serializer._load_failed_nodes == []
    assert serializer._load_failed_connections == 0


def test_from_yaml_file_not_found(pipeline_serializer, mock_graph):
    """Test loading from non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Pipeline file not found"):
        pipeline_serializer.from_yaml_file("nonexistent.yaml", mock_graph)


def test_from_yaml_file_success(pipeline_serializer, temp_pipeline_file, mock_graph):
    """Test loading pipeline from YAML file."""
    # Mock graph.create_node to return mock nodes
    mock_node = Mock(spec=CuvisNodeAdapter)
    mock_node.name = Mock(return_value="normalizer")
    mock_node.set_pos = Mock()
    mock_node.set_name = Mock()
    mock_node.cuvis_hparams = {}
    mock_node.cuvis_execution_stages = {"always"}
    mock_graph.create_node.return_value = mock_node

    metadata = pipeline_serializer.from_yaml_file(temp_pipeline_file, mock_graph)

    assert metadata["name"] == "Test Pipeline"
    assert metadata["description"] == "A test pipeline"
    assert mock_graph.clear_session.called
    mock_graph.create_node.assert_called()


def test_from_config_invalid_raises_error(pipeline_serializer, mock_graph):
    """Test loading invalid config raises ValueError."""
    invalid_config = {"invalid": "config"}

    with pytest.raises(ValueError, match="Invalid pipeline configuration"):
        pipeline_serializer.from_config(invalid_config, mock_graph)


def test_from_config_clears_graph(pipeline_serializer, sample_pipeline_config, mock_graph):
    """Test that from_config clears the graph."""
    # Mock successful node creation
    mock_node = Mock(spec=CuvisNodeAdapter)
    mock_node.name = Mock(return_value="test_node")
    mock_node.set_pos = Mock()
    mock_node.set_name = Mock()
    mock_node.input_ports = Mock(return_value=[])
    mock_node.output_ports = Mock(return_value=[])
    mock_graph.create_node.return_value = mock_node

    pipeline_serializer.from_config(sample_pipeline_config, mock_graph)

    mock_graph.clear_session.assert_called_once()


def test_from_config_creates_nodes(pipeline_serializer, sample_pipeline_config, mock_graph):
    """Test that from_config creates nodes from config."""
    # Mock successful node creation
    mock_node = Mock(spec=CuvisNodeAdapter)
    mock_node.name = Mock(return_value="test_node")
    mock_node.set_pos = Mock()
    mock_node.set_name = Mock()
    mock_node.input_ports = Mock(return_value=[])
    mock_node.output_ports = Mock(return_value=[])
    mock_graph.create_node.return_value = mock_node

    metadata = pipeline_serializer.from_config(sample_pipeline_config, mock_graph)

    # Should create 2 nodes from sample config
    assert mock_graph.create_node.call_count >= 1
    assert metadata["name"] == "Test Pipeline"


def test_parse_connection_string_valid(pipeline_serializer):
    """Test parsing valid connection strings."""
    result = pipeline_serializer._parse_connection_string("node1.outputs.port1")
    assert result == ("node1", "outputs", "port1")

    result = pipeline_serializer._parse_connection_string("normalizer.inputs.cube")
    assert result == ("normalizer", "inputs", "cube")


def test_parse_connection_string_invalid(pipeline_serializer):
    """Test parsing invalid connection strings returns None."""
    assert pipeline_serializer._parse_connection_string("invalid") is None
    assert pipeline_serializer._parse_connection_string("node.port") is None
    assert pipeline_serializer._parse_connection_string("") is None


def test_parse_connection_string_with_dots_in_node_name(pipeline_serializer):
    """Test parsing connection strings with dots in node name."""
    result = pipeline_serializer._parse_connection_string("my.node.name.outputs.port1")
    assert result == ("my.node.name", "outputs", "port1")


def test_to_config_empty_graph(pipeline_serializer, mock_graph):
    """Test converting empty graph to config."""
    mock_graph.all_nodes.return_value = []

    config = pipeline_serializer.to_config(mock_graph)

    assert "metadata" in config
    assert "nodes" in config
    assert "connections" in config
    assert len(config["nodes"]) == 0
    assert len(config["connections"]) == 0


def test_to_config_with_metadata(pipeline_serializer, mock_graph):
    """Test converting graph to config with metadata."""
    mock_graph.all_nodes.return_value = []
    metadata = {"name": "Custom Pipeline", "description": "Test"}

    config = pipeline_serializer.to_config(mock_graph, metadata)

    assert config["metadata"]["name"] == "Custom Pipeline"
    assert config["metadata"]["description"] == "Test"


def test_to_config_with_nodes(pipeline_serializer, mock_graph):
    """Test converting graph with nodes to config."""
    # Create mock node with cuvis config
    mock_node = Mock(spec=CuvisNodeAdapter)
    mock_node.name = Mock(return_value="test_node")
    mock_node.get_cuvis_config = Mock(return_value={
        "class": "cuvis_ai.node.test.TestNode",
        "name": "test_node",
        "params": {"param1": "value1"}
    })
    mock_node.output_ports = Mock(return_value=[])

    mock_graph.all_nodes.return_value = [mock_node]

    config = pipeline_serializer.to_config(mock_graph)

    assert len(config["nodes"]) == 1
    assert config["nodes"][0]["class"] == "cuvis_ai.node.test.TestNode"
    assert config["nodes"][0]["name"] == "test_node"


def test_to_config_with_connections(pipeline_serializer, mock_graph):
    """Test converting graph with connections to config."""
    # Create mock source node
    mock_output_port = Mock()
    mock_output_port.name = Mock(return_value="out1")
    mock_output_port.connected_ports = Mock(return_value=[])

    mock_source = Mock(spec=CuvisNodeAdapter)
    mock_source.name = Mock(return_value="source")
    mock_source.get_cuvis_config = Mock(return_value={
        "class": "cuvis_ai.node.Source",
        "name": "source",
        "params": {}
    })
    mock_source.output_ports = Mock(return_value=[mock_output_port])

    mock_graph.all_nodes.return_value = [mock_source]

    config = pipeline_serializer.to_config(mock_graph)

    assert "connections" in config
    assert isinstance(config["connections"], list)


def test_to_yaml_file_creates_directory(pipeline_serializer, mock_graph, tmp_path):
    """Test that to_yaml_file creates parent directory if needed."""
    mock_graph.all_nodes.return_value = []

    output_path = tmp_path / "subdir" / "pipeline.yaml"
    pipeline_serializer.to_yaml_file(mock_graph, output_path)

    assert output_path.exists()
    assert output_path.parent.exists()


def test_to_yaml_file_writes_valid_yaml(pipeline_serializer, mock_graph, tmp_path):
    """Test that to_yaml_file writes valid YAML content."""
    mock_graph.all_nodes.return_value = []

    output_path = tmp_path / "pipeline.yaml"
    metadata = {"name": "Test", "description": "Test pipeline"}
    pipeline_serializer.to_yaml_file(mock_graph, output_path, metadata)

    assert output_path.exists()

    # Read and verify content
    import yaml
    with open(output_path, "r") as f:
        content = yaml.safe_load(f)

    assert content["metadata"]["name"] == "Test"
    assert "nodes" in content
    assert "connections" in content


def test_to_yaml_string(pipeline_serializer, mock_graph):
    """Test converting graph to YAML string."""
    mock_graph.all_nodes.return_value = []

    yaml_str = pipeline_serializer.to_yaml_string(mock_graph)

    assert isinstance(yaml_str, str)
    assert "metadata" in yaml_str
    assert "nodes" in yaml_str
    assert "connections" in yaml_str


def test_from_yaml_string(pipeline_serializer, mock_graph):
    """Test loading from YAML string."""
    yaml_str = """
metadata:
  name: Test Pipeline
  description: From string
nodes:
  - class: cuvis_ai.node.test.TestNode
    name: test
    params: {}
connections: []
"""

    # Mock node creation
    mock_node = Mock(spec=CuvisNodeAdapter)
    mock_node.name = Mock(return_value="test")
    mock_node.set_pos = Mock()
    mock_node.set_name = Mock()
    mock_node.input_ports = Mock(return_value=[])
    mock_node.output_ports = Mock(return_value=[])
    mock_graph.create_node.return_value = mock_node

    metadata = pipeline_serializer.from_yaml_string(yaml_str, mock_graph)

    assert metadata["name"] == "Test Pipeline"
    assert metadata["description"] == "From string"


def test_auto_layout_empty_graph(pipeline_serializer, mock_graph):
    """Test auto layout with empty graph doesn't crash."""
    mock_graph.all_nodes.return_value = []

    # Should not raise exception
    pipeline_serializer._auto_layout(mock_graph)


def test_auto_layout_positions_nodes(pipeline_serializer, mock_graph):
    """Test auto layout positions nodes in columns."""
    # Create mock nodes
    mock_node1 = Mock(spec=CuvisNodeAdapter)
    mock_node1.name = Mock(return_value="node1")
    mock_node1.input_ports = Mock(return_value=[])
    mock_node1.output_ports = Mock(return_value=[])
    mock_node1.set_pos = Mock()

    mock_node2 = Mock(spec=CuvisNodeAdapter)
    mock_node2.name = Mock(return_value="node2")
    mock_node2.input_ports = Mock(return_value=[])
    mock_node2.output_ports = Mock(return_value=[])
    mock_node2.set_pos = Mock()

    mock_graph.all_nodes.return_value = [mock_node1, mock_node2]

    pipeline_serializer._auto_layout(mock_graph)

    # Verify nodes were positioned
    mock_node1.set_pos.assert_called_once()
    mock_node2.set_pos.assert_called_once()


def test_load_warnings_for_missing_nodes(pipeline_serializer, mock_graph):
    """Test that warnings are generated for missing node classes."""
    config = {
        "metadata": {"name": "Test"},
        "nodes": [
            {
                "class": "cuvis_ai.node.NonExistent",
                "name": "missing",
                "params": {}
            }
        ],
        "connections": []
    }

    # Mock create_node to return a placeholder
    mock_node = Mock(spec=CuvisNodeAdapter)
    mock_node.name = Mock(return_value="missing")
    mock_node.set_pos = Mock()
    mock_node.set_name = Mock()
    mock_node.input_ports = Mock(return_value=[])
    mock_node.output_ports = Mock(return_value=[])
    mock_graph.create_node.return_value = mock_node

    pipeline_serializer.from_config(config, mock_graph)

    # Should have warnings about missing nodes
    assert len(pipeline_serializer.last_load_warnings) > 0
    assert any("Missing node classes" in w for w in pipeline_serializer.last_load_warnings)


def test_create_placeholder_class(pipeline_serializer):
    """Test creating placeholder class for unknown nodes."""
    placeholder_class = pipeline_serializer._create_placeholder_class(
        "cuvis_ai.node.unknown.UnknownNode"
    )

    assert issubclass(placeholder_class, CuvisNodeAdapter)
    assert "UnknownNode" in placeholder_class.NODE_NAME
    assert "Unknown" in placeholder_class.NODE_NAME


def test_round_trip_validation_identical(pipeline_serializer, sample_pipeline_config, mock_graph):
    """Test round-trip validation with identical configs."""
    mock_graph.all_nodes.return_value = []

    # For identical configs (both empty), should be valid
    is_valid, differences = pipeline_serializer.validate_round_trip(
        {"metadata": {}, "nodes": [], "connections": []},
        mock_graph
    )

    assert is_valid
    assert len(differences) == 0


def test_round_trip_validation_missing_node(pipeline_serializer, mock_graph):
    """Test round-trip validation detects missing nodes."""
    original_config = {
        "metadata": {},
        "nodes": [{"class": "TestNode", "name": "test", "params": {}}],
        "connections": []
    }

    mock_graph.all_nodes.return_value = []  # Empty graph

    is_valid, differences = pipeline_serializer.validate_round_trip(
        original_config,
        mock_graph
    )

    assert not is_valid
    assert any("Missing node" in d for d in differences)
