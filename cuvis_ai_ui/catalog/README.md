# Bundled plugin catalog

21 plugin manifests mirrored from cuvis-ai `v0.22.6` (`cuvis_ai/configs/plugins/`).
The UI registers each one with the server at startup; the node palette is built
from their `capabilities`.

Do not edit these files by hand. Regenerate them for a new cuvis-ai release:

    uv run python scripts/regenerate_catalog.py --tag <cuvis-ai tag>
