"""Tests for node introspection utilities."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from cuvis_ai_ui.adapters.node_introspector import (
    import_node_class,
    extract_port_specs,
    enrich_node_info,
    enrich_node_list,
    _normalize_specs,
    _spec_to_dict,
    _infer_default_specs,
)
from cuvis_ai_schemas.pipeline.ports import PortSpec


def test_import_node_class_invalid_path():
    """Test importing with invalid path returns None."""
    result = import_node_class("invalid")
    assert result is None

    result = import_node_class("single_part")
    assert result is None


@patch('cuvis_ai_ui.adapters.node_introspector.importlib.import_module')
def test_import_node_class_import_error(mock_import):
    """Test that import errors are handled gracefully."""
    mock_import.side_effect = ImportError("Module not found")

    result = import_node_class("module.ClassName")
    assert result is None


@patch('cuvis_ai_ui.adapters.node_introspector.importlib.import_module')
def test_import_node_class_success(mock_import):
    """Test successful import returns the class."""
    mock_module = Mock()
    mock_class = Mock()
    mock_module.ClassName = mock_class
    mock_import.return_value = mock_module

    result = import_node_class("module.ClassName")
    assert result == mock_class
    mock_import.assert_called_once_with("module")


def test_extract_port_specs_with_attributes():
    """Test extracting port specs from class attributes."""
    class TestNode:
        input_specs = [{"name": "in1", "dtype": "float32"}]
        output_specs = [{"name": "out1", "dtype": "float32"}]

    input_specs, output_specs = extract_port_specs(TestNode)

    assert len(input_specs) == 1
    assert input_specs[0]["name"] == "in1"
    assert len(output_specs) == 1
    assert output_specs[0]["name"] == "out1"


def test_extract_port_specs_with_private_attributes():
    """Test extracting port specs from private attributes."""
    class TestNode:
        _input_specs = [{"name": "in1", "dtype": "float32"}]
        _output_specs = [{"name": "out1", "dtype": "float32"}]

    input_specs, output_specs = extract_port_specs(TestNode)

    assert len(input_specs) == 1
    assert len(output_specs) == 1


def test_extract_port_specs_with_uppercase_attributes():
    """Test extracting port specs from uppercase attributes."""
    class TestNode:
        INPUT_SPECS = [{"name": "in1", "dtype": "float32"}]
        OUTPUT_SPECS = [{"name": "out1", "dtype": "float32"}]

    input_specs, output_specs = extract_port_specs(TestNode)

    assert len(input_specs) == 1
    assert len(output_specs) == 1


def test_extract_port_specs_with_methods():
    """Test extracting port specs from methods."""
    class TestNode:
        @staticmethod
        def get_input_specs():
            return [{"name": "in1", "dtype": "float32"}]

        @staticmethod
        def get_output_specs():
            return [{"name": "out1", "dtype": "float32"}]

    input_specs, output_specs = extract_port_specs(TestNode)

    assert len(input_specs) == 1
    assert len(output_specs) == 1


def test_extract_port_specs_with_no_specs():
    """Test extracting port specs from class with no specs (infers defaults)."""
    class GenericNode:
        pass

    input_specs, output_specs = extract_port_specs(GenericNode)

    # Should infer default cube input/output
    assert len(input_specs) >= 1
    assert len(output_specs) >= 1


def test_normalize_specs_from_list_of_dicts():
    """Test normalizing specs from list of dicts."""
    specs = [{"name": "port1", "dtype": "float32"}]
    result = _normalize_specs(specs)

    assert len(result) == 1
    assert result[0]["name"] == "port1"


def test_normalize_specs_from_dict():
    """Test normalizing specs from dict mapping name -> spec."""
    specs = {
        "port1": {"dtype": "float32"},
        "port2": {"dtype": "int64"}
    }
    result = _normalize_specs(specs)

    assert len(result) == 2
    names = [s["name"] for s in result]
    assert "port1" in names
    assert "port2" in names


def test_normalize_specs_from_port_spec_objects():
    """Test normalizing specs from PortSpec objects."""
    # PortSpec doesn't have name field - names come from dict keys
    spec1 = PortSpec(dtype="float32", shape=(-1,), description="First port", optional=False)
    spec2 = PortSpec(dtype="int64", shape=(-1,), description="Second port", optional=True)

    specs = [spec1, spec2]
    result = _normalize_specs(specs)

    assert len(result) == 2
    # PortSpec objects converted to dicts don't have name field
    assert result[0]["dtype"] == "float32"
    assert result[0]["optional"] is False
    assert result[1]["dtype"] == "int64"
    assert result[1]["optional"] is True


def test_normalize_specs_none_returns_empty():
    """Test that normalizing None returns empty list."""
    result = _normalize_specs(None)
    assert result == []


def test_spec_to_dict_from_port_spec():
    """Test converting PortSpec to dict."""
    # PortSpec doesn't have name field - it's stored separately as dict key
    spec = PortSpec(dtype="float32", shape=(-1, -1), description="Test port", optional=False)
    result = _spec_to_dict(spec)

    # _spec_to_dict only returns fields that exist in PortSpec
    assert "name" not in result  # PortSpec doesn't have name field
    assert result["dtype"] == "float32"
    assert result["shape"] == (-1, -1)
    assert result["description"] == "Test port"
    assert result["optional"] is False


def test_spec_to_dict_from_generic_object():
    """Test converting generic object with attributes to dict."""
    class FakeSpec:
        name = "test"
        dtype = "float32"
        optional = False

    spec = FakeSpec()
    result = _spec_to_dict(spec)

    assert result["name"] == "test"
    assert result["dtype"] == "float32"
    assert result["optional"] is False


def test_infer_default_specs_generic():
    """Test inferring default specs for generic node."""
    class GenericNode:
        pass

    input_specs, output_specs = _infer_default_specs(GenericNode)

    assert len(input_specs) >= 1
    assert len(output_specs) >= 1
    assert input_specs[0]["name"] == "cube"
    assert output_specs[0]["name"] == "cube"


def test_infer_default_specs_data_loader():
    """Test inferring specs for data loader node."""
    class DataLoader:
        pass

    input_specs, output_specs = _infer_default_specs(DataLoader)

    # Data loaders have no inputs, multiple outputs
    assert len(input_specs) == 0
    assert len(output_specs) >= 1


def test_infer_default_specs_loss_node():
    """Test inferring specs for loss function node."""
    class MyLoss:
        pass

    input_specs, output_specs = _infer_default_specs(MyLoss)

    # Loss nodes take predictions + targets, output loss
    assert len(input_specs) >= 2
    assert len(output_specs) >= 1
    assert any("predictions" in s["name"] for s in input_specs)
    assert any("targets" in s["name"] for s in input_specs)


def test_infer_default_specs_metric_node():
    """Test inferring specs for metric node."""
    class AccuracyMetric:
        pass

    input_specs, output_specs = _infer_default_specs(AccuracyMetric)

    # Metrics similar to loss
    assert len(input_specs) >= 1
    assert len(output_specs) >= 1
    assert any("predictions" in s["name"] for s in input_specs)


def test_infer_default_specs_band_selector():
    """Test inferring specs for band selector node."""
    class BandSelector:
        pass

    input_specs, output_specs = _infer_default_specs(BandSelector)

    # Band selectors take cube + wavelengths
    assert len(input_specs) >= 1
    assert any("cube" in s["name"] for s in input_specs)


def test_enrich_node_info_with_specs(sample_node_info):
    """Test enriching node info that already has specs."""
    enriched = enrich_node_info(sample_node_info)

    assert "input_specs" in enriched
    assert "output_specs" in enriched
    assert len(enriched["input_specs"]) == 1
    assert len(enriched["output_specs"]) == 1


def test_enrich_node_info_without_specs():
    """Test enriching node info missing specs adds empty lists."""
    node_info = {
        "class_name": "TestNode",
        "full_path": "test.TestNode"
    }

    enriched = enrich_node_info(node_info)

    assert "input_specs" in enriched
    assert "output_specs" in enriched
    assert enriched["input_specs"] == []
    assert enriched["output_specs"] == []


def test_enrich_node_list():
    """Test enriching a list of node infos."""
    nodes = [
        {"class_name": "Node1", "full_path": "test.Node1"},
        {"class_name": "Node2", "full_path": "test.Node2", "input_specs": []}
    ]

    enriched = enrich_node_list(nodes)

    assert len(enriched) == 2
    assert all("input_specs" in n for n in enriched)
    assert all("output_specs" in n for n in enriched)


def test_normalize_specs_with_simple_values():
    """Test normalizing dict with simple values creates minimal specs."""
    specs = {"port1": "float32", "port2": "int64"}
    result = _normalize_specs(specs)

    assert len(result) == 2
    assert all("name" in s for s in result)
    assert all("dtype" in s for s in result)
