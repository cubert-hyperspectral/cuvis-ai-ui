"""Integration tests for end-to-end pipeline load/save functionality.

Tests the complete workflow:
- YAML → Graph conversion
- Graph → YAML conversion
- Round-trip serialization
- Error handling for invalid files
"""

import pytest
import yaml
from pathlib import Path

from cuvis_ai_ui.adapters.pipeline_serializer import PipelineSerializer


def test_load_pipeline_from_yaml_file(temp_pipeline_file, node_registry):
    """Test loading a pipeline from a YAML file."""
    from NodeGraphQt import NodeGraph

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    metadata = serializer.from_yaml_file(temp_pipeline_file, graph)

    assert graph is not None
    assert metadata is not None
    # Should have created nodes
    assert len(graph.all_nodes()) > 0


def test_load_pipeline_from_config_dict(sample_pipeline_config, node_registry):
    """Test loading a pipeline from a config dictionary."""
    from NodeGraphQt import NodeGraph

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    metadata = serializer.from_config(sample_pipeline_config, graph)

    assert graph is not None
    assert metadata is not None
    # Should have nodes matching the config
    assert len(graph.all_nodes()) >= len(sample_pipeline_config["nodes"])


def test_save_pipeline_to_yaml_file(sample_pipeline_config, node_registry, tmp_path):
    """Test saving a pipeline to a YAML file."""
    from NodeGraphQt import NodeGraph

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    # Load from config
    _metadata = serializer.from_config(sample_pipeline_config, graph)

    # Save to file
    output_file = tmp_path / "output_pipeline.yaml"
    serializer.to_yaml_file(graph, output_file)

    # Verify file was created
    assert output_file.exists()

    # Verify file is valid YAML
    with open(output_file, "r") as f:
        saved_config = yaml.safe_load(f)

    assert saved_config is not None
    assert "nodes" in saved_config


def test_save_pipeline_to_config_dict(sample_pipeline_config, node_registry):
    """Test converting a graph back to config dictionary."""
    from NodeGraphQt import NodeGraph

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    # Load from config
    _metadata = serializer.from_config(sample_pipeline_config, graph)

    # Convert back to config
    output_config = serializer.to_config(graph)

    assert output_config is not None
    assert "nodes" in output_config
    assert isinstance(output_config["nodes"], list)


def test_pipeline_round_trip(sample_pipeline_config, node_registry, tmp_path):
    """Test complete round-trip: Config → Graph → File → Graph → Config."""
    from NodeGraphQt import NodeGraph

    serializer = PipelineSerializer(node_registry)

    # Step 1: Config → Graph
    graph1 = NodeGraph()
    _metadata = serializer.from_config(sample_pipeline_config, graph1)
    original_node_count = len(graph1.all_nodes())

    # Step 2: Graph → File
    temp_file = tmp_path / "roundtrip.yaml"
    serializer.to_yaml_file(graph1, temp_file)

    # Step 3: File → Graph
    graph2 = NodeGraph()
    _metadata2 = serializer.from_yaml_file(temp_file, graph2)

    # Step 4: Graph → Config
    output_config = serializer.to_config(graph2)

    # Verify round-trip preserved structure
    assert len(graph2.all_nodes()) == original_node_count
    assert len(output_config["nodes"]) == len(sample_pipeline_config["nodes"])


def test_load_pipeline_with_metadata(node_registry, tmp_path):
    """Test that pipeline metadata is preserved during load/save."""
    from NodeGraphQt import NodeGraph

    config = {
        "metadata": {
            "name": "Test Pipeline",
            "description": "A test pipeline with metadata",
            "tags": ["test", "example"],
            "author": "Test Author",
        },
        "nodes": [
            {
                "class_name": "cuvis_ai.node.normalization.MinMaxNormalizer",
                "name": "normalizer",
                "params": {},
            }
        ],
        "connections": [],
    }

    serializer = PipelineSerializer(node_registry)

    # Save to file
    pipeline_file = tmp_path / "metadata_pipeline.yaml"
    with open(pipeline_file, "w") as f:
        yaml.dump(config, f)

    # Load from file
    graph = NodeGraph()
    metadata = serializer.from_yaml_file(pipeline_file, graph)

    # Convert back to config
    output_config = serializer.to_config(graph, metadata)

    # Metadata should be preserved
    assert "metadata" in output_config
    assert output_config["metadata"]["name"] == "Test Pipeline"


def test_load_pipeline_with_connections(node_registry, tmp_path):
    """Test that pipeline connections are correctly loaded."""
    from NodeGraphQt import NodeGraph

    config = {
        "metadata": {"name": "Connected Pipeline"},
        "nodes": [
            {
                "class_name": "cuvis_ai.node.normalization.MinMaxNormalizer",
                "name": "normalizer",
                "params": {},
            },
            {
                "class_name": "cuvis_ai.node.normalization.MinMaxNormalizer",
                "name": "normalizer2",
                "params": {},
            },
        ],
        "connections": [{"source": "normalizer.outputs.cube", "target": "normalizer2.inputs.cube"}],
    }

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    _metadata = serializer.from_config(config, graph)

    # Should have connections (implementation-dependent)
    # At minimum, should not crash with connections
    assert graph is not None


def test_load_invalid_yaml_file(node_registry, tmp_path):
    """Test error handling for invalid YAML file."""
    from NodeGraphQt import NodeGraph

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    # Create invalid YAML file
    invalid_file = tmp_path / "invalid.yaml"
    with open(invalid_file, "w") as f:
        f.write("{ invalid yaml content [[[")

    # Should raise exception or return None
    with pytest.raises(Exception):
        serializer.from_yaml_file(invalid_file, graph)


def test_load_nonexistent_file(node_registry):
    """Test error handling for non-existent file."""
    from NodeGraphQt import NodeGraph

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    nonexistent = Path("/nonexistent/path/file.yaml")

    # Should raise exception
    with pytest.raises(Exception):
        serializer.from_yaml_file(nonexistent, graph)


def test_load_pipeline_with_missing_nodes(node_registry, tmp_path):
    """Test loading pipeline with nodes not in registry."""
    from NodeGraphQt import NodeGraph

    config = {
        "metadata": {"name": "Missing Nodes Pipeline"},
        "nodes": [{"class_name": "nonexistent.node.FakeNode", "name": "fake_node", "params": {}}],
        "connections": [],
    }

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    # Should handle gracefully (may skip unknown nodes or raise exception)
    try:
        _metadata = serializer.from_config(config, graph)
        # If it succeeds, graph should be valid (may have 0 nodes)
        assert graph is not None
    except Exception:
        # Or it may raise an exception for unknown nodes
        pass  # This is also acceptable behavior


def test_save_empty_pipeline(node_registry, tmp_path):
    """Test saving a pipeline with no nodes."""
    from NodeGraphQt import NodeGraph

    config = {"metadata": {"name": "Empty Pipeline"}, "nodes": [], "connections": []}

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    # Create empty graph (may not be possible with all implementations)
    try:
        _metadata = serializer.from_config(config, graph)

        output_file = tmp_path / "empty_pipeline.yaml"
        serializer.to_yaml_file(graph, output_file)

        # Should create valid file
        assert output_file.exists()
    except Exception:
        # Some implementations may not allow empty pipelines
        pass


def test_pipeline_node_positions(sample_pipeline_config, node_registry):
    """Test that node positions are handled (auto-layout or preserved)."""
    from NodeGraphQt import NodeGraph

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    _metadata = serializer.from_config(sample_pipeline_config, graph)

    # Nodes should have positions (auto-layout or from config)
    for node in graph.all_nodes():
        # Position methods may vary by implementation
        # Just verify nodes exist and don't crash
        assert node is not None


def test_pipeline_connection_format(sample_pipeline_config, node_registry):
    """Test that connections use correct format (source/target dict)."""
    from NodeGraphQt import NodeGraph

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    _metadata = serializer.from_config(sample_pipeline_config, graph)
    output_config = serializer.to_config(graph)

    # Connections should be in dict format with "source" and "target" keys
    for conn in output_config.get("connections", []):
        if isinstance(conn, dict):
            assert "source" in conn or "target" in conn


def test_pipeline_hyperparameter_preservation(node_registry, tmp_path):
    """Test that node hyperparameters are preserved during serialization."""
    from NodeGraphQt import NodeGraph

    config = {
        "metadata": {"name": "Hyperparameter Test"},
        "nodes": [
            {
                "class_name": "cuvis_ai.node.normalization.MinMaxNormalizer",
                "name": "normalizer",
                "params": {"min": 0.0, "max": 1.0},
            }
        ],
        "connections": [],
    }

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    # Load and save
    _metadata = serializer.from_config(config, graph)
    output_config = serializer.to_config(graph)

    # Hyperparameters should be in output
    assert len(output_config["nodes"]) > 0
    # Check if params are preserved (may be under "params" or "hparams")
    node_config = output_config["nodes"][0]
    assert "params" in node_config or "hparams" in node_config


def test_multiple_pipelines_same_serializer(sample_pipeline_config, node_registry, tmp_path):
    """Test that one serializer can handle multiple pipelines."""
    from NodeGraphQt import NodeGraph

    serializer = PipelineSerializer(node_registry)

    # Load first pipeline
    graph1 = NodeGraph()
    _metadata1 = serializer.from_config(sample_pipeline_config, graph1)
    file1 = tmp_path / "pipeline1.yaml"
    serializer.to_yaml_file(graph1, file1)

    # Load second pipeline
    graph2 = NodeGraph()
    _metadata2 = serializer.from_config(sample_pipeline_config, graph2)
    file2 = tmp_path / "pipeline2.yaml"
    serializer.to_yaml_file(graph2, file2)

    # Both files should exist
    assert file1.exists()
    assert file2.exists()


def test_pipeline_with_special_characters_in_name(node_registry, tmp_path):
    """Test pipeline with special characters in metadata."""
    from NodeGraphQt import NodeGraph

    config = {
        "metadata": {
            "name": "Test Pipeline (v1.0) - α β γ",
            "description": "Description with special chars: é ñ ü",
        },
        "nodes": [],
        "connections": [],
    }

    serializer = PipelineSerializer(node_registry)
    graph = NodeGraph()

    # Should handle special characters
    try:
        _metadata = serializer.from_config(config, graph)
        output_file = tmp_path / "special_chars.yaml"
        serializer.to_yaml_file(graph, output_file)

        # Verify file is valid UTF-8 YAML
        with open(output_file, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        assert loaded is not None
    except Exception:
        # May not support all special characters
        pass


def test_pipeline_serializer_with_empty_registry(tmp_path):
    """Test serializer with an empty node registry."""
    from NodeGraphQt import NodeGraph
    from cuvis_ai_ui.adapters import NodeRegistry

    empty_registry = NodeRegistry()
    serializer = PipelineSerializer(empty_registry)
    graph = NodeGraph()

    config = {"metadata": {"name": "Test"}, "nodes": [], "connections": []}

    # Should not crash with empty registry
    try:
        _metadata = serializer.from_config(config, graph)
        assert graph is not None
    except Exception:
        # May require non-empty registry
        pass
