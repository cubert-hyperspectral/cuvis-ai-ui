"""Unit tests for port_helpers module."""

import pytest
from unittest.mock import Mock, MagicMock

from cuvis_ai_schemas.pipeline.ports import PortSpec
from cuvis_ai_ui.adapters.port_helpers import (
    create_input_port,
    create_output_port,
    get_port_spec,
    validate_connection,
    format_port_tooltip,
)


@pytest.fixture
def mock_node():
    """Mock NodeGraphQt node."""
    node = MagicMock()
    node._cuvis_port_specs = {}
    return node


@pytest.fixture
def sample_port_spec():
    """Sample PortSpec for testing."""
    return PortSpec(
        dtype="float32",
        shape=(-1, -1, -1, -1),
        description="Test port",
        optional=False
    )


@pytest.fixture
def multi_input_port_spec():
    """PortSpec with multi_input enabled."""
    spec = PortSpec(
        dtype="float32",
        shape=(-1,),
        description="Multi-input port",
        optional=False
    )
    spec.multi_input = True
    return spec


def test_create_input_port(mock_node, sample_port_spec):
    """Test creating an input port from PortSpec."""
    port = create_input_port(mock_node, "test_port", sample_port_spec)

    # Verify add_input was called
    mock_node.add_input.assert_called_once()

    # Verify call arguments
    call_kwargs = mock_node.add_input.call_args.kwargs
    assert call_kwargs["name"] == "test_port"
    assert "color" in call_kwargs
    assert call_kwargs["display_name"] is True

    # Verify spec was stored
    assert "test_port" in mock_node._cuvis_port_specs
    assert mock_node._cuvis_port_specs["test_port"] == sample_port_spec


def test_create_input_port_with_multi_input(mock_node, multi_input_port_spec):
    """Test creating a multi-input port."""
    port = create_input_port(mock_node, "multi_port", multi_input_port_spec)

    mock_node.add_input.assert_called_once()
    call_kwargs = mock_node.add_input.call_args.kwargs
    assert call_kwargs["multi_input"] is True


def test_create_output_port(mock_node, sample_port_spec):
    """Test creating an output port from PortSpec."""
    port = create_output_port(mock_node, "test_port", sample_port_spec)

    # Verify add_output was called
    mock_node.add_output.assert_called_once()

    # Verify call arguments
    call_kwargs = mock_node.add_output.call_args.kwargs
    assert call_kwargs["name"] == "test_port"
    assert "color" in call_kwargs
    assert call_kwargs["display_name"] is True

    # Verify spec was stored
    assert "test_port" in mock_node._cuvis_port_specs
    assert mock_node._cuvis_port_specs["test_port"] == sample_port_spec


def test_create_multiple_ports(mock_node):
    """Test creating multiple ports on the same node."""
    spec1 = PortSpec(dtype="float32", shape=(-1,), description="", optional=False)
    spec2 = PortSpec(dtype="int64", shape=(-1,), description="", optional=False)

    create_input_port(mock_node, "port1", spec1)
    create_output_port(mock_node, "port2", spec2)

    # Both specs should be stored
    assert "port1" in mock_node._cuvis_port_specs
    assert "port2" in mock_node._cuvis_port_specs
    assert len(mock_node._cuvis_port_specs) == 2


def test_get_port_spec(mock_node, sample_port_spec):
    """Test retrieving a PortSpec from a node."""
    # Store a spec
    mock_node._cuvis_port_specs["test_port"] = sample_port_spec

    # Retrieve it
    retrieved_spec = get_port_spec(mock_node, "test_port")

    assert retrieved_spec == sample_port_spec


def test_get_port_spec_not_found(mock_node):
    """Test retrieving a non-existent PortSpec."""
    retrieved_spec = get_port_spec(mock_node, "nonexistent")

    assert retrieved_spec is None


def test_get_port_spec_no_specs_attribute():
    """Test get_port_spec on a node without _cuvis_port_specs."""
    from unittest.mock import Mock

    # Use Mock instead of MagicMock to avoid auto-creating attributes
    node = Mock(spec=[])  # Empty spec means no attributes

    retrieved_spec = get_port_spec(node, "any_port")

    assert retrieved_spec is None


def test_validate_connection_compatible_types():
    """Test validating a connection between compatible ports."""
    source_node = MagicMock()
    target_node = MagicMock()

    source_spec = PortSpec(dtype="float32", shape=(-1, -1), optional=False)
    target_spec = PortSpec(dtype="float32", shape=(-1, -1), optional=False)

    source_node._cuvis_port_specs = {"out": source_spec}
    target_node._cuvis_port_specs = {"in": target_spec}

    is_valid, error_msg = validate_connection(source_node, "out", target_node, "in")

    assert is_valid is True
    assert error_msg == ""


def test_validate_connection_incompatible_types():
    """Test validating a connection between incompatible ports."""
    source_node = MagicMock()
    target_node = MagicMock()

    source_spec = PortSpec(dtype="float32", shape=(-1,), description="", optional=False)
    target_spec = PortSpec(dtype="int64", shape=(-1,), description="", optional=False)

    source_node._cuvis_port_specs = {"out": source_spec}
    target_node._cuvis_port_specs = {"in": target_spec}

    is_valid, error_msg = validate_connection(source_node, "out", target_node, "in")

    assert is_valid is False
    # Error message from cuvis-ai-schemas PortSpec.is_compatible_with()
    assert ("Dtype mismatch" in error_msg or "Type mismatch" in error_msg)
    assert "float32" in error_msg
    assert "int64" in error_msg


def test_validate_connection_any_type_compatible():
    """Test that 'any' type is compatible with all types."""
    source_node = MagicMock()
    target_node = MagicMock()

    source_spec = PortSpec(dtype="any", shape=(-1,), description="", optional=False)
    target_spec = PortSpec(dtype="float32", shape=(-1,), description="", optional=False)

    source_node._cuvis_port_specs = {"out": source_spec}
    target_node._cuvis_port_specs = {"in": target_spec}

    is_valid, error_msg = validate_connection(source_node, "out", target_node, "in")

    assert is_valid is True
    assert error_msg == ""


def test_validate_connection_to_any_type_compatible():
    """Test that any type can connect to 'any' type."""
    source_node = MagicMock()
    target_node = MagicMock()

    source_spec = PortSpec(dtype="int64", shape=(-1,), description="", optional=False)
    target_spec = PortSpec(dtype="any", shape=(-1,), description="", optional=False)

    source_node._cuvis_port_specs = {"out": source_spec}
    target_node._cuvis_port_specs = {"in": target_spec}

    is_valid, error_msg = validate_connection(source_node, "out", target_node, "in")

    assert is_valid is True
    assert error_msg == ""


def test_validate_connection_source_spec_not_found():
    """Test validation when source port spec is missing."""
    source_node = MagicMock()
    target_node = MagicMock()

    target_spec = PortSpec(dtype="float32", shape=(-1,), description="", optional=False)

    source_node._cuvis_port_specs = {}
    target_node._cuvis_port_specs = {"in": target_spec}

    is_valid, error_msg = validate_connection(source_node, "out", target_node, "in")

    assert is_valid is False
    assert "Source port" in error_msg
    assert "not found" in error_msg


def test_validate_connection_target_spec_not_found():
    """Test validation when target port spec is missing."""
    source_node = MagicMock()
    target_node = MagicMock()

    source_spec = PortSpec(dtype="float32", shape=(-1,), description="", optional=False)

    source_node._cuvis_port_specs = {"out": source_spec}
    target_node._cuvis_port_specs = {}

    is_valid, error_msg = validate_connection(source_node, "out", target_node, "in")

    assert is_valid is False
    assert "Target port" in error_msg
    assert "not found" in error_msg


def test_validate_connection_with_is_compatible_method():
    """Test validation using PortSpec.is_compatible_with method if available."""
    source_node = MagicMock()
    target_node = MagicMock()

    # Create specs with is_compatible_with method
    source_spec = MagicMock(spec=PortSpec)
    source_spec.dtype = "float32"
    source_spec.is_compatible_with.return_value = (True, "")

    target_spec = MagicMock(spec=PortSpec)
    target_spec.dtype = "float32"

    source_node._cuvis_port_specs = {"out": source_spec}
    target_node._cuvis_port_specs = {"in": target_spec}

    is_valid, error_msg = validate_connection(source_node, "out", target_node, "in")

    # Should call the is_compatible_with method with 3 arguments (target_spec, source_node, target_node)
    source_spec.is_compatible_with.assert_called_once_with(target_spec, source_node, target_node)
    assert is_valid is True
    assert error_msg == ""


def test_format_port_tooltip(sample_port_spec):
    """Test formatting a port tooltip."""
    tooltip = format_port_tooltip(sample_port_spec)

    assert isinstance(tooltip, str)
    # Should contain port information (HTML format with <br> instead of \n)
    assert "float32" in tooltip or "Test port" in tooltip


def test_format_port_tooltip_with_optional():
    """Test tooltip for an optional port."""
    spec = PortSpec(dtype="int64", shape=(-1,), description="Optional port", optional=True)

    tooltip = format_port_tooltip(spec)

    assert isinstance(tooltip, str)
    # Should indicate optional status somehow
    assert len(tooltip) > 0


def test_port_spec_storage_persistence(mock_node):
    """Test that port specs persist across multiple port creations."""
    spec1 = PortSpec(dtype="float32", shape=(-1,), description="", optional=False)
    spec2 = PortSpec(dtype="int64", shape=(-1,), description="", optional=False)

    # Create first port
    create_input_port(mock_node, "port1", spec1)
    assert len(mock_node._cuvis_port_specs) == 1

    # Create second port
    create_input_port(mock_node, "port2", spec2)
    assert len(mock_node._cuvis_port_specs) == 2

    # Both specs should still be accessible
    assert get_port_spec(mock_node, "port1") == spec1
    assert get_port_spec(mock_node, "port2") == spec2


def test_create_port_color_from_dtype():
    """Test that port color is determined by dtype."""
    mock_node = MagicMock()
    mock_node._cuvis_port_specs = {}

    # Create ports with different dtypes
    float_spec = PortSpec(dtype="float32", shape=(-1,), description="", optional=False)
    int_spec = PortSpec(dtype="int64", shape=(-1,), description="", optional=False)

    create_input_port(mock_node, "float_port", float_spec)
    create_input_port(mock_node, "int_port", int_spec)

    # Verify add_input was called twice with color argument
    assert mock_node.add_input.call_count == 2

    # Both calls should have a color argument
    for call in mock_node.add_input.call_args_list:
        assert "color" in call.kwargs
