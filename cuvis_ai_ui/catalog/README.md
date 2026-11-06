# Bundled plugin catalog

18 released plugin manifests mirrored from cuvis-ai `v0.22.6` (`cuvis_ai/configs/plugins/`),
each pinned to a git repo and tag. The UI registers each one with the server at
startup; the node palette is built from their `capabilities`. Manifests with a
local `path:` source are not bundled; load those from the app's plugins folder or
with `--plugins-dir`.

Do not edit these files by hand. Regenerate them for a new cuvis-ai release:

    uv run python scripts/regenerate_catalog.py --tag <cuvis-ai tag>
