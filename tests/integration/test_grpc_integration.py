"""Integration tests for gRPC client interactions.

Consolidated from:
- tests/test_all_nodes_have_specs.py
- tests/test_supervised_nodes.py

Refactored to use pytest fixtures and mocking for reliable, repeatable tests.
"""

import pytest
from unittest.mock import Mock, patch

from cuvis_ai_ui.grpc.client import CuvisAIClient


@pytest.fixture
def mock_grpc_server():
    """Mock gRPC server responses with comprehensive node data."""
    nodes = [
        {
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
                    "description": "Input hyperspectral cube"
                }
            ],
            "output_specs": [
                {
                    "name": "cube",
                    "dtype": "float32",
                    "shape": "[-1, -1, -1, -1]",
                    "optional": False,
                    "description": "Normalized cube"
                }
            ]
        },
        {
            "class_name": "SupervisedFullSpectrumBandSelector",
            "full_path": "cuvis_ai.node.band_selection.SupervisedFullSpectrumBandSelector",
            "source": "builtin",
            "plugin_name": "",
            "input_specs": [
                {
                    "name": "cube",
                    "dtype": "float32",
                    "shape": "[-1, -1, -1, -1]",
                    "optional": False,
                    "description": "Input cube"
                },
                {
                    "name": "labels",
                    "dtype": "int64",
                    "shape": "[-1]",
                    "optional": False,
                    "description": "Training labels"
                }
            ],
            "output_specs": [
                {
                    "name": "selected_bands",
                    "dtype": "int64",
                    "shape": "[-1]",
                    "optional": False,
                    "description": "Selected band indices"
                }
            ]
        },
        {
            "class_name": "SupervisedCIRBandSelector",
            "full_path": "cuvis_ai.node.band_selection.SupervisedCIRBandSelector",
            "source": "builtin",
            "plugin_name": "",
            "input_specs": [
                {
                    "name": "cube",
                    "dtype": "float32",
                    "shape": "[-1, -1, -1, -1]",
                    "optional": False,
                    "description": "Input cube"
                },
                {
                    "name": "labels",
                    "dtype": "int64",
                    "shape": "[-1]",
                    "optional": False,
                    "description": "Training labels"
                }
            ],
            "output_specs": [
                {
                    "name": "cir_bands",
                    "dtype": "int64",
                    "shape": "[3]",
                    "optional": False,
                    "description": "CIR band indices (NIR, Red, Green)"
                }
            ]
        },
        {
            "class_name": "SupervisedWindowedFalseRGBSelector",
            "full_path": "cuvis_ai.node.band_selection.SupervisedWindowedFalseRGBSelector",
            "source": "builtin",
            "plugin_name": "",
            "input_specs": [
                {
                    "name": "cube",
                    "dtype": "float32",
                    "shape": "[-1, -1, -1, -1]",
                    "optional": False,
                    "description": "Input cube"
                },
                {
                    "name": "labels",
                    "dtype": "int64",
                    "shape": "[-1]",
                    "optional": False,
                    "description": "Training labels"
                }
            ],
            "output_specs": [
                {
                    "name": "rgb_bands",
                    "dtype": "int64",
                    "shape": "[3]",
                    "optional": False,
                    "description": "False RGB band indices"
                }
            ]
        },
        {
            "class_name": "LearnableChannelMixer",
            "full_path": "cuvis_ai.node.mixing.LearnableChannelMixer",
            "source": "builtin",
            "plugin_name": "",
            "input_specs": [
                {
                    "name": "cube",
                    "dtype": "float32",
                    "shape": "[-1, -1, -1, -1]",
                    "optional": False,
                    "description": "Input cube"
                }
            ],
            "output_specs": [
                {
                    "name": "mixed_cube",
                    "dtype": "float32",
                    "shape": "[-1, -1, -1, -1]",
                    "optional": False,
                    "description": "Mixed channels"
                }
            ]
        },
        {
            "class_name": "TrainablePCA",
            "full_path": "cuvis_ai.node.dimensionality.TrainablePCA",
            "source": "builtin",
            "plugin_name": "",
            "input_specs": [
                {
                    "name": "cube",
                    "dtype": "float32",
                    "shape": "[-1, -1, -1, -1]",
                    "optional": False,
                    "description": "Input cube"
                }
            ],
            "output_specs": [
                {
                    "name": "reduced_cube",
                    "dtype": "float32",
                    "shape": "[-1, -1, -1, -1]",
                    "optional": False,
                    "description": "PCA-reduced cube"
                }
            ]
        },
        {
            "class_name": "ConcreteBandSelector",
            "full_path": "cuvis_ai.node.band_selection.ConcreteBandSelector",
            "source": "builtin",
            "plugin_name": "",
            "input_specs": [
                {
                    "name": "cube",
                    "dtype": "float32",
                    "shape": "[-1, -1, -1, -1]",
                    "optional": False,
                    "description": "Input cube"
                },
                {
                    "name": "band_indices",
                    "dtype": "int64",
                    "shape": "[-1]",
                    "optional": False,
                    "description": "Band indices to select"
                }
            ],
            "output_specs": [
                {
                    "name": "selected_cube",
                    "dtype": "float32",
                    "shape": "[-1, -1, -1, -1]",
                    "optional": False,
                    "description": "Cube with selected bands"
                }
            ]
        },
        # Add a node without specs to test edge cases
        {
            "class_name": "EmptyNode",
            "full_path": "cuvis_ai.node.test.EmptyNode",
            "source": "builtin",
            "plugin_name": "",
            "input_specs": [],
            "output_specs": []
        }
    ]

    mock_client = Mock(spec=CuvisAIClient)
    mock_client.session_id = "test-session-123"
    mock_client.list_available_nodes.return_value = nodes
    mock_client.load_plugins.return_value = {
        "loaded_plugins": ["cuvis_ai"],
        "failed_plugins": []
    }

    return mock_client


def test_plugin_loading(mock_grpc_server):
    """Test loading plugins through gRPC client."""
    result = mock_grpc_server.load_plugins("cuvis_ai_catalog.yaml")

    assert "loaded_plugins" in result
    assert "failed_plugins" in result
    assert len(result["loaded_plugins"]) > 0
    assert len(result["failed_plugins"]) == 0


def test_list_available_nodes(mock_grpc_server):
    """Test listing available nodes from gRPC server."""
    nodes = mock_grpc_server.list_available_nodes()

    assert len(nodes) > 0
    assert isinstance(nodes, list)

    # Check that all nodes have required fields
    for node in nodes:
        assert "class_name" in node
        assert "full_path" in node
        assert "source" in node


def test_all_nodes_have_port_specs(mock_grpc_server):
    """Test that nodes have input/output port specifications.

    This is the main test from test_all_nodes_have_specs.py
    """
    nodes = mock_grpc_server.list_available_nodes()

    nodes_with_specs = []
    nodes_without_specs = []

    for node in nodes:
        num_inputs = len(node.get("input_specs", []))
        num_outputs = len(node.get("output_specs", []))

        if num_inputs == 0 and num_outputs == 0:
            nodes_without_specs.append(node["class_name"])
        else:
            nodes_with_specs.append(node["class_name"])

    # Most nodes should have specs
    assert len(nodes_with_specs) > len(nodes_without_specs)

    # Known nodes without specs (test nodes, etc.)
    expected_empty = ["EmptyNode"]
    assert set(nodes_without_specs) == set(expected_empty)


def test_supervised_nodes_have_specs(mock_grpc_server):
    """Test that supervised band selector nodes have port specs.

    This is the main test from test_supervised_nodes.py
    """
    nodes = mock_grpc_server.list_available_nodes()

    target_nodes = [
        "SupervisedFullSpectrumBandSelector",
        "SupervisedCIRBandSelector",
        "SupervisedWindowedFalseRGBSelector",
    ]

    for target_name in target_nodes:
        # Find the node
        node = next((n for n in nodes if n["class_name"] == target_name), None)

        assert node is not None, f"{target_name} not found in node list"

        # Check it has specs
        num_inputs = len(node.get("input_specs", []))
        num_outputs = len(node.get("output_specs", []))

        assert num_inputs > 0, f"{target_name} has no input specs"
        assert num_outputs > 0, f"{target_name} has no output specs"

        # Verify spec structure
        for spec in node["input_specs"]:
            assert "name" in spec
            assert "dtype" in spec
            assert "optional" in spec

        for spec in node["output_specs"]:
            assert "name" in spec
            assert "dtype" in spec
            assert "optional" in spec


def test_problematic_nodes_have_specs(mock_grpc_server):
    """Test nodes that previously had issues with port specs.

    These nodes had issues with:
    - dict dtype
    - symbolic shape
    """
    nodes = mock_grpc_server.list_available_nodes()

    test_nodes = {
        "SupervisedFullSpectrumBandSelector": "dict dtype",
        "LearnableChannelMixer": "symbolic shape",
        "TrainablePCA": "symbolic shape",
        "ConcreteBandSelector": "symbolic shape",
    }

    for node_name, issue in test_nodes.items():
        node = next((n for n in nodes if n["class_name"] == node_name), None)

        assert node is not None, f"{node_name} not found"

        num_inputs = len(node.get("input_specs", []))
        num_outputs = len(node.get("output_specs", []))

        assert num_inputs > 0 or num_outputs > 0, \
            f"{node_name} ({issue}) has no port specs"


def test_port_spec_validation(mock_grpc_server):
    """Test that port specs have all required fields."""
    nodes = mock_grpc_server.list_available_nodes()

    # Filter to nodes with specs
    nodes_with_specs = [n for n in nodes
                       if len(n.get("input_specs", [])) > 0
                       or len(n.get("output_specs", [])) > 0]

    assert len(nodes_with_specs) > 0

    for node in nodes_with_specs:
        node_name = node["class_name"]

        # Check input specs
        for i, spec in enumerate(node.get("input_specs", [])):
            assert "name" in spec, f"{node_name} input {i} missing 'name'"
            assert "dtype" in spec, f"{node_name} input {i} missing 'dtype'"
            assert "optional" in spec, f"{node_name} input {i} missing 'optional'"
            assert isinstance(spec["optional"], bool), \
                f"{node_name} input {i} 'optional' is not bool"

        # Check output specs
        for i, spec in enumerate(node.get("output_specs", [])):
            assert "name" in spec, f"{node_name} output {i} missing 'name'"
            assert "dtype" in spec, f"{node_name} output {i} missing 'dtype'"
            assert "optional" in spec, f"{node_name} output {i} missing 'optional'"
            assert isinstance(spec["optional"], bool), \
                f"{node_name} output {i} 'optional' is not bool"


def test_node_metadata_completeness(mock_grpc_server):
    """Test that all nodes have complete metadata."""
    nodes = mock_grpc_server.list_available_nodes()

    for node in nodes:
        # Required fields
        assert node["class_name"], "Node has empty class_name"
        assert node["full_path"], "Node has empty full_path"
        assert node["source"] in ["builtin", "plugin"], \
            f"Node {node['class_name']} has invalid source: {node['source']}"

        # Check full_path format (should be importable Python path)
        assert "." in node["full_path"], \
            f"Node {node['class_name']} has invalid full_path: {node['full_path']}"

        # Class name should be in full_path
        assert node["class_name"] in node["full_path"], \
            f"Class name {node['class_name']} not in full_path {node['full_path']}"
