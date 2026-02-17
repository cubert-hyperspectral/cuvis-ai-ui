"""Test script to verify pipeline serialization with Pydantic validation.

This script tests:
1. Saving pipelines with correct {"source": "...", "target": "..."} format
2. Pydantic validation of pipeline configs
"""

import yaml
from cuvis_ai_schemas.pipeline import PipelineConfig, ConnectionConfig, NodeConfig


def test_connection_formats():
    """Test that connection format is supported."""
    print("=" * 60)
    print("TEST 1: Connection Format Validation")
    print("=" * 60)

    # Test 1: Dict format with source/target keys
    print("\n1. Testing dict format (source/target keys)...")
    config_dict_format = {
        "metadata": {"name": "Test Pipeline"},
        "nodes": [
            {"class_name": "test.Node1", "name": "node1"},
            {"class_name": "test.Node2", "name": "node2"},
        ],
        "connections": [{"source": "node1.outputs.out", "target": "node2.inputs.in"}],
    }

    try:
        pipeline = PipelineConfig.from_dict(config_dict_format)
        print("   ✓ Dict format validated successfully")
        print(
            f"   Connection: source={pipeline.connections[0].source}, target={pipeline.connections[0].target}"
        )
    except Exception as e:
        print(f"   ✗ Dict format failed: {e}")

    # Test 2: Verify output format uses source/target
    print("\n2. Testing output format...")
    output_dict = pipeline.to_dict()

    print(f"   Output connections: {output_dict['connections']}")
    if isinstance(output_dict["connections"][0], dict):
        if "source" in output_dict["connections"][0] and "target" in output_dict["connections"][0]:
            print("   ✓ Output uses correct source/target format")
        else:
            print("   ✗ Output missing source/target keys")
    else:
        print("   ✗ Output is not dict format")


def test_validation_errors():
    """Test that validation catches errors."""
    print("\n" + "=" * 60)
    print("TEST 2: Validation Error Detection")
    print("=" * 60)

    # Test 1: Invalid connection format (missing target)
    print("\n1. Testing invalid connection format...")
    try:
        config = {
            "nodes": [{"class_name": "test.Node", "name": "node1"}],
            "connections": [
                {"source": "node1.outputs.out"}  # Missing 'target'
            ],
        }
        PipelineConfig.from_dict(config)
        print("   ✗ Should have failed validation")
    except Exception as e:
        print(f"   ✓ Caught error: {type(e).__name__}")

    # Test 2: Invalid port format
    print("\n2. Testing invalid port format...")
    try:
        config = {
            "nodes": [{"class_name": "test.Node", "name": "node1"}],
            "connections": [
                {"source": "node1.out", "target": "node1.in"}  # Missing .outputs/.inputs
            ],
        }
        PipelineConfig.from_dict(config)
        print("   ✗ Should have failed validation")
    except Exception as e:
        print(f"   ✓ Caught error: {type(e).__name__}")


def test_yaml_output():
    """Test that YAML output has correct format."""
    print("\n" + "=" * 60)
    print("TEST 3: YAML Output Format")
    print("=" * 60)

    # Create a pipeline config
    pipeline = PipelineConfig(
        metadata={"name": "Example Pipeline", "description": "Test pipeline"},
        nodes=[
            NodeConfig(
                class_name="cuvis_ai.node.normalizer.MinMaxNormalizer",
                name="normalizer",
                params={"min": 0.0, "max": 1.0},
            ),
            NodeConfig(class_name="cuvis_ai.node.model.SimpleModel", name="model", params={}),
        ],
        connections=[
            ConnectionConfig(source="normalizer.outputs.cube", target="model.inputs.data"),
        ],
    )

    # Convert to dict and then to YAML
    config_dict = pipeline.to_dict()
    yaml_str = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

    print("\nGenerated YAML:")
    print("-" * 60)
    print(yaml_str)
    print("-" * 60)

    # Check format
    if "source:" in yaml_str and "target:" in yaml_str:
        print("\n✓ YAML uses correct source/target format for connections")
    else:
        print("\n✗ YAML does not use source/target format")

    # Verify it can be reloaded
    try:
        reloaded = yaml.safe_load(yaml_str)
        _pipeline2 = PipelineConfig.from_dict(reloaded)
        print("✓ YAML can be reloaded successfully")
    except Exception as e:
        print(f"✗ Failed to reload YAML: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Pipeline Serialization Validation Tests")
    print("=" * 60)

    test_connection_formats()
    test_validation_errors()
    test_yaml_output()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
