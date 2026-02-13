"""Node introspection utility for extracting port specs from cuvis-ai classes.

This module provides utilities to dynamically import cuvis-ai node classes
and extract their input/output port specifications for visualization.
"""

import importlib
from typing import Any

from loguru import logger

from cuvis_ai_schemas.pipeline.ports import PortSpec


def import_node_class(full_path: str) -> type | None:
    """Dynamically import a node class from its full path.

    Args:
        full_path: Full import path like "cuvis_ai.node.normalization.MinMaxNormalizer"

    Returns:
        The node class, or None if import failed
    """
    try:
        parts = full_path.rsplit(".", 1)
        if len(parts) != 2:
            logger.warning(f"Invalid class path: {full_path}")
            return None

        module_path, class_name = parts
        module = importlib.import_module(module_path)
        return getattr(module, class_name, None)

    except ImportError as e:
        logger.debug(f"Failed to import {full_path}: {e}")
        return None
    except Exception as e:
        logger.debug(f"Error importing {full_path}: {e}")
        return None


def extract_port_specs(node_class: type) -> tuple[list[dict], list[dict]]:
    """Extract input and output port specifications from a cuvis-ai node class.

    Supports multiple patterns used by cuvis-ai nodes:
    - Class attributes: input_specs, output_specs
    - Private attributes: _input_specs, _output_specs
    - Properties that return specs
    - Methods: get_input_specs(), get_output_specs()

    Args:
        node_class: The cuvis-ai node class

    Returns:
        Tuple of (input_specs, output_specs) as lists of dicts
    """
    input_specs: list[dict] = []
    output_specs: list[dict] = []

    # Try different attribute patterns
    input_attrs = ["input_specs", "_input_specs", "INPUT_SPECS"]
    output_attrs = ["output_specs", "_output_specs", "OUTPUT_SPECS"]

    # Try to get input specs
    for attr in input_attrs:
        if hasattr(node_class, attr):
            specs = getattr(node_class, attr, None)
            if specs is not None:
                input_specs = _normalize_specs(specs)
                break

    # Try to get output specs
    for attr in output_attrs:
        if hasattr(node_class, attr):
            specs = getattr(node_class, attr, None)
            if specs is not None:
                output_specs = _normalize_specs(specs)
                break

    # If no specs found, try methods
    if not input_specs:
        for method_name in ["get_input_specs", "input_spec"]:
            if hasattr(node_class, method_name):
                try:
                    method = getattr(node_class, method_name)
                    if callable(method):
                        # Try calling as class method (no instance)
                        specs = method()
                        input_specs = _normalize_specs(specs)
                        break
                except (TypeError, AttributeError):
                    pass

    if not output_specs:
        for method_name in ["get_output_specs", "output_spec"]:
            if hasattr(node_class, method_name):
                try:
                    method = getattr(node_class, method_name)
                    if callable(method):
                        specs = method()
                        output_specs = _normalize_specs(specs)
                        break
                except (TypeError, AttributeError):
                    pass

    # If still no specs, create default input/output based on class inspection
    if not input_specs and not output_specs:
        input_specs, output_specs = _infer_default_specs(node_class)

    return input_specs, output_specs


def _normalize_specs(specs: Any) -> list[dict]:
    """Normalize port specifications to a list of dicts.

    Handles various formats:
    - List of PortSpec objects
    - List of dicts
    - Dict mapping name -> spec
    - Single spec

    Args:
        specs: Raw specs in various formats

    Returns:
        List of normalized spec dicts
    """
    if specs is None:
        return []

    if isinstance(specs, dict):
        # Dict mapping name -> spec
        result = []
        for name, spec in specs.items():
            if isinstance(spec, dict):
                spec_dict = spec.copy()
                spec_dict.setdefault("name", name)
                result.append(spec_dict)
            elif hasattr(spec, "__dict__"):
                spec_dict = _spec_to_dict(spec)
                spec_dict.setdefault("name", name)
                result.append(spec_dict)
            else:
                # Simple value, create minimal spec
                result.append({"name": name, "dtype": str(spec)})
        return result

    if isinstance(specs, (list, tuple)):
        result = []
        for spec in specs:
            if isinstance(spec, dict):
                result.append(spec)
            elif hasattr(spec, "__dict__"):
                result.append(_spec_to_dict(spec))
            elif hasattr(spec, "name"):
                # PortSpec-like object
                result.append(_spec_to_dict(spec))
        return result

    if hasattr(specs, "__dict__"):
        return [_spec_to_dict(specs)]

    return []


def _spec_to_dict(spec: Any) -> dict:
    """Convert a spec object to a dict.

    Args:
        spec: A PortSpec or similar object

    Returns:
        Dict representation
    """
    result = {}

    # Common attributes
    for attr in ["name", "dtype", "shape", "optional", "display_name", "description"]:
        if hasattr(spec, attr):
            value = getattr(spec, attr)
            if value is not None:
                result[attr] = value

    # Handle PortSpec specifically
    if isinstance(spec, PortSpec):
        # PortSpec doesn't have a 'name' field - name is stored as dict key elsewhere
        # Return spec fields without name
        return {
            "dtype": spec.dtype,
            "shape": spec.shape,
            "description": spec.description,
            "optional": spec.optional,
        }

    return result


def _infer_default_specs(node_class: type) -> tuple[list[dict], list[dict]]:
    """Infer default port specs from class name/structure.

    Used as fallback when no explicit specs are defined.

    Args:
        node_class: The node class

    Returns:
        Tuple of (input_specs, output_specs)
    """
    class_name = node_class.__name__.lower()

    # Default: one cube input, one cube output
    input_specs = [{"name": "cube", "dtype": "cube", "optional": False}]
    output_specs = [{"name": "cube", "dtype": "cube", "optional": False}]

    # Customize based on class name patterns
    if "data" in class_name or "loader" in class_name:
        # Data nodes typically have no inputs, multiple outputs
        input_specs = []
        output_specs = [
            {"name": "cube", "dtype": "cube", "optional": False},
            {"name": "mask", "dtype": "mask", "optional": True},
            {"name": "wavelengths", "dtype": "wavelengths", "optional": True},
        ]

    elif "loss" in class_name or "criterion" in class_name:
        # Loss nodes take predictions and targets, output loss value
        input_specs = [
            {"name": "predictions", "dtype": "tensor", "optional": False},
            {"name": "targets", "dtype": "tensor", "optional": False},
        ]
        output_specs = [{"name": "loss", "dtype": "scalar", "optional": False}]

    elif "metric" in class_name:
        # Metric nodes similar to loss
        input_specs = [
            {"name": "predictions", "dtype": "tensor", "optional": False},
            {"name": "targets", "dtype": "tensor", "optional": True},
        ]
        output_specs = [{"name": "metric", "dtype": "scalar", "optional": False}]

    elif "visualiz" in class_name or "monitor" in class_name:
        # Visualization nodes take cube, output image
        input_specs = [{"name": "cube", "dtype": "cube", "optional": False}]
        output_specs = [{"name": "image", "dtype": "image", "optional": False}]

    elif "selector" in class_name or "band" in class_name:
        # Band selection nodes
        input_specs = [
            {"name": "cube", "dtype": "cube", "optional": False},
            {"name": "wavelengths", "dtype": "wavelengths", "optional": True},
        ]
        output_specs = [
            {"name": "cube", "dtype": "cube", "optional": False},
            {"name": "indices", "dtype": "indices", "optional": True},
        ]

    elif "label" in class_name or "mapper" in class_name:
        # Label mapping nodes
        input_specs = [{"name": "mask", "dtype": "mask", "optional": False}]
        output_specs = [{"name": "labels", "dtype": "labels", "optional": False}]

    return input_specs, output_specs


def enrich_node_info(node_info: dict[str, Any]) -> dict[str, Any]:
    """Enrich node info with port specifications.

    Note: Port specs are now provided by the gRPC server. This function
    only ensures that specs are present, adding empty lists if missing.

    Args:
        node_info: Node info from gRPC with input_specs and output_specs

    Returns:
        Node info with guaranteed input_specs and output_specs fields
    """
    # Ensure specs are present (should already be provided by gRPC)
    enriched = node_info.copy()
    enriched.setdefault("input_specs", [])
    enriched.setdefault("output_specs", [])

    return enriched


def enrich_node_list(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich a list of node infos with port specifications.

    Args:
        nodes: List of basic node info dicts

    Returns:
        List of enriched node info dicts
    """
    enriched = []
    for node_info in nodes:
        enriched.append(enrich_node_info(node_info))
    return enriched
