"""Smoke tests for the bundled cuvis_ai_catalog.yaml.

The refactored plugin loader requires each manifest ``provides`` entry to be a
CatalogNodeEntry (FQCN class_name + palette metadata), and the node palette is
populated straight from this inline catalog (the server no longer imports plugin
code). These tests guard that the shipped catalog still matches that contract.
"""

from cuvis_ai_schemas.catalog import CatalogNodeEntry

from cuvis_ai_ui.settings.plugins import build_manifest, get_default_plugin_entries


def test_bundled_catalog_loads():
    entries = get_default_plugin_entries()
    assert entries, "bundled cuvis_ai_catalog.yaml produced no plugin entries"


def test_bundled_catalog_is_git_sourced_with_provides():
    manifest = build_manifest(get_default_plugin_entries(), enabled_only=False)
    plugins = manifest["plugins"]
    assert "cuvis_ai_builtin" in plugins

    builtin = plugins["cuvis_ai_builtin"]
    assert builtin.get("repo"), "bundled catalog must use a git source"
    assert builtin.get("tag"), "bundled catalog must pin a tag"
    provides = builtin.get("provides")
    assert isinstance(provides, list) and provides


def test_bundled_catalog_provides_validate_as_catalog_node_entries():
    manifest = build_manifest(get_default_plugin_entries(), enabled_only=False)
    provides = manifest["plugins"]["cuvis_ai_builtin"]["provides"]
    for raw in provides:
        entry = CatalogNodeEntry(**raw)  # raises on any schema violation
        assert "." in entry.class_name, f"not fully-qualified: {entry.class_name!r}"
