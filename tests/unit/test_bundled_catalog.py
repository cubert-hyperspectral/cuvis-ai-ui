"""Smoke tests for the bundled cuvis_ai_catalog.yaml.

The refactored plugin loader requires each manifest ``capabilities`` entry to be
a PluginCapabilityEntry (FQCN class_name + palette metadata), and the node
palette is populated straight from this catalog (the server no longer imports
plugin code). The catalog file is now ONE bare plugin manifest (a ``name``, a
source, and its ``capabilities`` list) rather than a ``plugins:``-wrapped map.
These tests guard that the shipped catalog still matches that contract.
"""

from cuvis_ai_schemas.plugin import PluginCapabilityEntry

from cuvis_ai_ui.settings.plugins import build_manifest, get_default_plugin_entries


def _builtin_manifest():
    manifest = build_manifest(get_default_plugin_entries(), enabled_only=False)
    assert isinstance(manifest, list)
    matches = [m for m in manifest if m.get("name") == "cuvis_ai_builtin"]
    assert len(matches) == 1, "bundled catalog must declare exactly one cuvis_ai_builtin manifest"
    return matches[0]


def test_bundled_catalog_loads():
    entries = get_default_plugin_entries()
    assert entries, "bundled cuvis_ai_catalog.yaml produced no plugin entries"
    # One file is one bare plugin.
    assert len(entries) == 1
    assert entries[0]["name"] == "cuvis_ai_builtin"


def test_bundled_catalog_is_git_sourced_with_capabilities():
    builtin = _builtin_manifest()
    assert builtin.get("repo"), "bundled catalog must use a git source"
    assert builtin.get("tag"), "bundled catalog must pin a tag"
    capabilities = builtin.get("capabilities")
    assert isinstance(capabilities, list) and capabilities


def test_bundled_catalog_capabilities_validate_as_capability_entries():
    capabilities = _builtin_manifest()["capabilities"]
    for raw in capabilities:
        entry = PluginCapabilityEntry(**raw)  # raises on any schema violation
        assert "." in entry.class_name, f"not fully-qualified: {entry.class_name!r}"
