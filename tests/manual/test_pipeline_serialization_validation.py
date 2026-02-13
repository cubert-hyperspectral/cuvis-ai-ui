"""Test script to verify pipeline serialization with Pydantic validation.

This script tests:
1. Saving pipelines with correct {"from": "...", "to": "..."} format
2. Loading pipelines with both formats (backward compatibility)
3. Pydantic validation of pipeline configs
"""

import yaml
from pathlib import Path
from cuvis_ai_schemas.pipeline import PipelineConfig, ConnectionConfig, NodeConfig


def test_connection_formats():
    """Test that both connection formats are supported."""
    print("=" * 60)
    print("TEST 1: Connection Format Validation")
    print("=" * 60)
    
    # Test 1: Dict format with from/to keys (CORRECT)
    print("\n1. Testing dict format (from/to keys)...")
    config_dict_format = {
        "metadata": {"name": "Test Pipeline"},
        "nodes": [
            {"class": "test.Node1", "name": "node1"},
            {"class": "test.Node2", "name": "node2"},
        ],
        "connections": [
            {"from": "node1.outputs.out", "to": "node2.inputs.in"}
        ]
    }
    
    try:
        pipeline = PipelineConfig.from_dict(config_dict_format)
        print("   ✓ Dict format validated successfully")
        print(f"   Connection: from={pipeline.connections[0].from_}, to={pipeline.connections[0].to}")
    except Exception as e:
        print(f"   ✗ Dict format failed: {e}")
    
    # Test 2: Legacy list format (BACKWARD COMPATIBLE)
    print("\n2. Testing legacy list format...")
    config_list_format = {
        "metadata": {"name": "Test Pipeline"},
        "nodes": [
            {"class": "test.Node1", "name": "node1"},
            {"class": "test.Node2", "name": "node2"},
        ],
        "connections": [
            ["node1.outputs.out", "node2.inputs.in"]  # Old format
        ]
    }
    
    try:
        pipeline = PipelineConfig.from_dict(config_list_format)
        print("   ✓ List format validated successfully (backward compatible)")
        print(f"   Connection: from={pipeline.connections[0].from_}, to={pipeline.connections[0].to}")
    except Exception as e:
        print(f"   ✗ List format failed: {e}")
    
    # Test 3: Verify output format uses from/to
    print("\n3. Testing output format...")
    pipeline = PipelineConfig.from_dict(config_list_format)
    output_dict = pipeline.to_dict()
    
    print(f"   Output connections: {output_dict['connections']}")
    if isinstance(output_dict['connections'][0], dict):
        if 'from' in output_dict['connections'][0] and 'to' in output_dict['connections'][0]:
            print("   ✓ Output uses correct from/to format")
        else:
            print("   ✗ Output missing from/to keys")
    else:
        print("   ✗ Output is not dict format")


def test_validation_errors():
    """Test that validation catches errors."""
    print("\n" + "=" * 60)
    print("TEST 2: Validation Error Detection")
    print("=" * 60)
    
    # Test 1: Invalid connection format
    print("\n1. Testing invalid connection format...")
    try:
        config = {
            "nodes": [{"class": "test.Node", "name": "node1"}],
            "connections": [
                {"from": "node1.outputs.out"}  # Missing 'to'
            ]
        }
        pipeline = PipelineConfig.from_dict(config)
        print("   ✗ Should have failed validation")
    except Exception as e:
        print(f"   ✓ Caught error: {type(e).__name__}")
    
    # Test 2: Connection references non-existent node
    print("\n2. Testing connection to non-existent node...")
    try:
        config = {
            "nodes": [{"class": "test.Node", "name": "node1"}],
            "connections": [
                {"from": "node1.outputs.out", "to": "node2.inputs.in"}  # node2 doesn't exist
            ]
        }
        pipeline = PipelineConfig.from_dict(config)
        errors = pipeline.validate_connections_reference_nodes()
        if errors:
            print(f"   ✓ Validation detected errors: {errors[0]}")
        else:
            print("   ✗ Should have detected missing node")
    except Exception as e:
        print(f"   ✓ Caught error: {type(e).__name__}: {e}")
    
    # Test 3: Invalid port format
    print("\n3. Testing invalid port format...")
    try:
        config = {
            "nodes": [{"class": "test.Node", "name": "node1"}],
            "connections": [
                {"from": "node1.out", "to": "node1.in"}  # Missing .outputs/.inputs
            ]
        }
        pipeline = PipelineConfig.from_dict(config)
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
            NodeConfig(class_="cuvis_ai.node.normalizer.MinMaxNormalizer", name="normalizer", hparams={"min": 0.0, "max": 1.0}),
            NodeConfig(class_="cuvis_ai.node.model.SimpleModel", name="model", hparams={}),
        ],
        connections=[
            ConnectionConfig(from_="normalizer.outputs.cube", to="model.inputs.data"),
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
    if "from:" in yaml_str and "to:" in yaml_str:
        print("\n✓ YAML uses correct from/to format for connections")
    else:
        print("\n✗ YAML does not use from/to format")
    
    # Verify it can be reloaded
    try:
        reloaded = yaml.safe_load(yaml_str)
        pipeline2 = PipelineConfig.from_dict(reloaded)
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
