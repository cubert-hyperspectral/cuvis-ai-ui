"""Port helpers for cuvis-ai to NodeGraphQt integration.

This module provides:
- Port creation helpers for NodeGraphQt nodes
- Connection validation logic based on PortSpec compatibility

Note: DTYPE_COLORS and PortDisplaySpec are imported directly from cuvis-ai-schemas,
which now includes comprehensive hyperspectral-specific type colors.
"""

from typing import Any

from cuvis_ai_schemas.extensions.ui import PortDisplaySpec
from cuvis_ai_schemas.pipeline.ports import PortSpec
from NodeGraphQt import BaseNode


def create_input_port(node: BaseNode, port_name: str, spec: PortSpec) -> Any:
    """Create an input port on a NodeGraphQt node from a PortSpec.

    Args:
        node: The NodeGraphQt node to add the port to
        port_name: Name for the port (PortSpec doesn't store names)
        spec: The port specification

    Returns:
        The created port object
    """
    display_spec = PortDisplaySpec(spec)

    port = node.add_input(
        name=port_name,
        color=display_spec.color,
        multi_input=getattr(spec, "multi_input", False),
        display_name=True,  # Boolean: show the port name
    )

    # Store the spec on the port for later validation
    if not hasattr(node, "_cuvis_port_specs"):
        node._cuvis_port_specs = {}
    node._cuvis_port_specs[port_name] = spec

    return port


def create_output_port(node: BaseNode, port_name: str, spec: PortSpec) -> Any:
    """Create an output port on a NodeGraphQt node from a PortSpec.

    Args:
        node: The NodeGraphQt node to add the port to
        port_name: Name for the port (PortSpec doesn't store names)
        spec: The port specification

    Returns:
        The created port object
    """
    display_spec = PortDisplaySpec(spec)

    port = node.add_output(
        name=port_name,
        color=display_spec.color,
        display_name=True,  # Boolean: show the port name
    )

    # Store the spec on the port for later validation
    if not hasattr(node, "_cuvis_port_specs"):
        node._cuvis_port_specs = {}
    node._cuvis_port_specs[port_name] = spec

    return port


def get_port_spec(node: BaseNode, port_name: str) -> PortSpec | None:
    """Get the PortSpec for a port on a node.

    Args:
        node: The NodeGraphQt node
        port_name: Name of the port

    Returns:
        PortSpec if found, None otherwise
    """
    specs = getattr(node, "_cuvis_port_specs", {})
    return specs.get(port_name)


def validate_connection(
    source_node: BaseNode,
    source_port_name: str,
    target_node: BaseNode,
    target_port_name: str,
) -> tuple[bool, str]:
    """Validate a connection between two ports.

    Uses PortSpec compatibility rules to determine if a connection
    between an output port and an input port is valid.

    Args:
        source_node: The node with the output port
        source_port_name: Name of the output port
        target_node: The node with the input port
        target_port_name: Name of the input port

    Returns:
        Tuple of (is_valid, error_message)
    """
    source_spec = get_port_spec(source_node, source_port_name)
    target_spec = get_port_spec(target_node, target_port_name)

    if source_spec is None:
        return False, f"Source port '{source_port_name}' spec not found"

    if target_spec is None:
        return False, f"Target port '{target_port_name}' spec not found"

    # Special handling for "any" type - it's compatible with everything
    if source_spec.dtype == "any" or target_spec.dtype == "any":
        return True, ""

    # Use PortSpec's is_compatible_with if available
    if hasattr(source_spec, "is_compatible_with"):
        return source_spec.is_compatible_with(target_spec, source_node, target_node)

    # Basic type compatibility check
    if source_spec.dtype == target_spec.dtype:
        return True, ""

    return False, f"Type mismatch: {source_spec.dtype} cannot connect to {target_spec.dtype}"


def format_port_tooltip(spec: PortSpec) -> str:
    """Generate a tooltip string for a port.

    Args:
        spec: The port specification

    Returns:
        HTML-formatted tooltip string
    """
    display_spec = PortDisplaySpec(spec)
    return display_spec.format_tooltip().replace("\\n", "<br>")
