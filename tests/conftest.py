"""Shared pytest fixtures for cuvis-ai-ui tests."""

import pytest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication

from cuvis_ai_ui.adapters import NodeRegistry
from cuvis_ai_ui.grpc.client import CuvisAIClient


@pytest.fixture(scope="session")
def qapp():
    """QApplication instance for Qt tests (session-scoped)."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_grpc_client():
    """Mock CuvisAIClient for testing without gRPC server."""
    client = Mock(spec=CuvisAIClient)
    client.session_id = "test-session-123"
    client.list_available_nodes.return_value = []
    client.load_plugins.return_value = {"loaded_plugins": [], "failed_plugins": []}
    return client


@pytest.fixture
def sample_node_info():
    """Sample node info dictionary."""
    return {
        "class_name": "MinMaxNormalizer",
        "full_path": "cuvis_ai.node.normalization.MinMaxNormalizer",
        "source": "builtin",
        "plugin_name": "",
        "input_specs": [
            {
                "name": "cube",
                "dtype": "float32",
                "shape": "[-1, -1, -1, -1]",
                "optional": False,
                "description": "Input hyperspectral cube",
            }
        ],
        "output_specs": [
            {
                "name": "cube",
                "dtype": "float32",
                "shape": "[-1, -1, -1, -1]",
                "optional": False,
                "description": "Normalized cube",
            }
        ],
    }


@pytest.fixture
def node_registry(sample_node_info):
    """NodeRegistry with sample nodes registered."""
    registry = NodeRegistry()
    registry.register_nodes([sample_node_info])
    return registry


@pytest.fixture
def sample_pipeline_config():
    """Sample pipeline configuration for testing."""
    return {
        "metadata": {"name": "Test Pipeline", "description": "A test pipeline", "tags": ["test"]},
        "nodes": [
            {
                "class": "cuvis_ai.node.normalization.MinMaxNormalizer",
                "name": "normalizer",
                "params": {"min": 0.0, "max": 1.0},
            },
            {"class": "cuvis_ai.node.model.SimpleModel", "name": "model", "params": {}},
        ],
        "connections": [{"from": "normalizer.outputs.cube", "to": "model.inputs.data"}],
    }


@pytest.fixture
def temp_pipeline_file(tmp_path, sample_pipeline_config):
    """Temporary pipeline YAML file for testing."""
    import yaml

    file_path = tmp_path / "test_pipeline.yaml"
    with open(file_path, "w") as f:
        yaml.dump(sample_pipeline_config, f)

    return file_path
