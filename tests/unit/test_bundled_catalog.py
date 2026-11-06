"""Tests for the bundled plugin catalog.

The UI ships every plugin manifest cuvis-ai keeps under ``cuvis_ai/configs/plugins/``
as package data in ``cuvis_ai_ui/catalog/``, one bare manifest per file. At startup
each one is registered with the server, which builds the node palette from the
manifests' ``capabilities``. These tests guard that the shipped files still match
the manifest schema and that the loader turns them into bundled plugin entries.
"""

from pathlib import Path

import pytest
import yaml
from cuvis_ai_schemas.plugin import parse_plugin_manifest

import cuvis_ai_ui
from cuvis_ai_ui.settings.plugins import (
    BUNDLED_SOURCE,
    build_manifest,
    get_catalog_dir,
    get_default_plugin_entries,
)

CATALOG_FILES = sorted(get_catalog_dir().glob("*.yaml"))


def test_catalog_lives_inside_the_package():
    # A wheel install has no repo root, so the catalog must ship under cuvis_ai_ui/.
    assert get_catalog_dir().parent == Path(cuvis_ai_ui.__file__).parent


def test_catalog_ships_the_released_cuvis_ai_plugins():
    names = [yaml.safe_load(path.read_text(encoding="utf-8"))["name"] for path in CATALOG_FILES]
    assert len(names) >= 18
    assert len(names) == len(set(names)), "two manifests share a plugin name"
    assert "cuvis_ai_builtin" in names


@pytest.mark.parametrize("path", CATALOG_FILES, ids=lambda p: p.stem)
def test_each_manifest_validates_and_pins_a_release(path):
    # A bundled local path would make a server install whatever sits there.
    manifest = parse_plugin_manifest(yaml.safe_load(path.read_text(encoding="utf-8")))
    assert getattr(manifest, "repo", None), f"{path.name} has no git repo source"
    assert getattr(manifest, "tag", None), f"{path.name} pins no tag"


def test_default_entries_are_bundled_one_per_file():
    entries = get_default_plugin_entries()
    assert len(entries) == len(CATALOG_FILES)
    assert {entry["source"] for entry in entries} == {BUNDLED_SOURCE}


def test_builtin_manifest_carries_port_specs():
    manifests = build_manifest(get_default_plugin_entries(), enabled_only=False)
    builtin = next(m for m in manifests if m["name"] == "cuvis_ai_builtin")
    nodes = [c for c in builtin["capabilities"] if c.get("kind", "node") == "node"]
    with_ports = [c for c in nodes if c.get("input_specs") or c.get("output_specs")]
    assert len(nodes) >= 150
    assert len(with_ports) >= 150


def test_built_manifests_validate():
    # What the UI sends over LoadPlugin.
    for manifest in build_manifest(get_default_plugin_entries(), enabled_only=False):
        parse_plugin_manifest(manifest)
