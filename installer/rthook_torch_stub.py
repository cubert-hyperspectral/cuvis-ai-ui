"""PyInstaller runtime hook: inject a lightweight torch stub.

The UI only uses cuvis_ai_schemas.pipeline.ports.PortSpec for display.
ports.py does ``import torch`` and references ``torch.dtype`` and
``torch.Tensor``, but no actual tensor computation happens in the UI.

By injecting this stub *before* the application code runs, we avoid
bundling the full torch package (~2 GB) into the installer.
"""

import sys
import types


def _make_torch_stub():
    """Build a minimal ``torch`` module with dtype and Tensor."""
    torch = types.ModuleType("torch")
    torch.__path__ = []  # pretend it's a package

    # --- torch.dtype stub ---------------------------------------------------
    class _dtype:
        """Minimal stand-in for torch.dtype."""

        def __init__(self, name="float32"):
            self._name = name

        def __repr__(self):
            return f"torch.{self._name}"

        def __eq__(self, other):
            return isinstance(other, _dtype) and self._name == other._name

        def __hash__(self):
            return hash(self._name)

    torch.dtype = _dtype

    # Common dtype instances that PortSpec.normalize_dtype may encounter
    for name in (
        "float16",
        "float32",
        "float64",
        "int8",
        "int16",
        "int32",
        "int64",
        "bool",
        "uint8",
        "bfloat16",
        "complex64",
        "complex128",
    ):
        setattr(torch, name, _dtype(name))

    # --- torch.Tensor stub --------------------------------------------------
    class _Tensor:
        """Minimal stand-in for torch.Tensor (used only as a sentinel type)."""

        pass

    torch.Tensor = _Tensor

    return torch


# Only install the stub if real torch is not already available
if "torch" not in sys.modules:
    sys.modules["torch"] = _make_torch_stub()
