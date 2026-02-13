"""Tests for plugin settings persistence."""

import json
from pathlib import Path

import pytest

from cuvis_ai_ui.settings.plugins import (
    PLUGIN_STORE_VERSION,
    _dedupe_entries,
    _normalize_entry,
    build_manifest,
    load_plugin_entries,
    merge_plugin_entries,
    reset_plugin_entries,
    save_plugin_entries,
    write_manifest_temp,
)


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _patch_store_path(tmp_path, monkeypatch):
    """Redirect the plugin store to a temp directory for every test."""
    store_file = tmp_path / "plugins.json"
    monkeypatch.setattr(
        "cuvis_ai_ui.settings.plugins.get_plugin_store_path",
        lambda: store_file,
    )
    return store_file


@pytest.fixture
def store_file(tmp_path):
    return tmp_path / "plugins.json"


def _make_entry(
    name="my_plugin",
    enabled=True,
    source="plugin",
    config=None,
    origin=None,
):
    """Helper to build a valid plugin entry dict."""
    entry = {"name": name, "enabled": enabled, "source": source}
    if config is not None:
        entry["config"] = config
    if origin is not None:
        entry["origin"] = origin
    return entry


# ── _normalize_entry ─────────────────────────────────────────────────


class TestNormalizeEntry:
    def test_valid_entry(self):
        entry = _make_entry(
            name="foo", enabled=True, source="manifest", config={"a": 1}, origin="/p"
        )
        result = _normalize_entry(entry)
        assert result is not None
        assert result["name"] == "foo"
        assert result["enabled"] is True
        assert result["source"] == "manifest"
        assert result["config"] == {"a": 1}
        assert result["origin"] == "/p"

    def test_none_input_returns_none(self):
        assert _normalize_entry(None) is None

    def test_string_input_returns_none(self):
        assert _normalize_entry("not a dict") is None

    def test_int_input_returns_none(self):
        assert _normalize_entry(42) is None

    def test_list_input_returns_none(self):
        assert _normalize_entry([1, 2]) is None

    def test_missing_name_returns_none(self):
        assert _normalize_entry({"enabled": True}) is None

    def test_empty_name_returns_none(self):
        assert _normalize_entry({"name": ""}) is None

    def test_non_string_name_returns_none(self):
        assert _normalize_entry({"name": 123}) is None

    def test_missing_config_defaults_to_empty_dict(self):
        result = _normalize_entry({"name": "x"})
        assert result["config"] == {}

    def test_non_dict_config_defaults_to_empty_dict(self):
        result = _normalize_entry({"name": "x", "config": "bad"})
        assert result["config"] == {}

    def test_missing_source_defaults_to_plugin(self):
        result = _normalize_entry({"name": "x"})
        assert result["source"] == "plugin"

    def test_empty_source_defaults_to_plugin(self):
        result = _normalize_entry({"name": "x", "source": ""})
        assert result["source"] == "plugin"

    def test_non_string_source_defaults_to_plugin(self):
        result = _normalize_entry({"name": "x", "source": 999})
        assert result["source"] == "plugin"

    def test_missing_origin_defaults_to_none(self):
        result = _normalize_entry({"name": "x"})
        assert result["origin"] is None

    def test_non_string_origin_defaults_to_none(self):
        result = _normalize_entry({"name": "x", "origin": 123})
        assert result["origin"] is None

    def test_enabled_defaults_to_true(self):
        result = _normalize_entry({"name": "x"})
        assert result["enabled"] is True

    def test_enabled_false(self):
        result = _normalize_entry({"name": "x", "enabled": False})
        assert result["enabled"] is False

    def test_enabled_coerced_to_bool(self):
        result = _normalize_entry({"name": "x", "enabled": 0})
        assert result["enabled"] is False

    def test_result_has_expected_keys(self):
        result = _normalize_entry({"name": "x"})
        assert set(result.keys()) == {"name", "enabled", "source", "config", "origin"}


# ── _dedupe_entries ──────────────────────────────────────────────────


class TestDedupeEntries:
    def test_no_duplicates_unchanged(self):
        entries = [
            _make_entry(name="a"),
            _make_entry(name="b"),
            _make_entry(name="c"),
        ]
        result = _dedupe_entries(entries)
        assert [e["name"] for e in result] == ["a", "b", "c"]

    def test_later_duplicate_overrides_earlier(self):
        e1 = _make_entry(name="a", source="old")
        e2 = _make_entry(name="a", source="new")
        result = _dedupe_entries([e1, e2])
        assert len(result) == 1
        assert result[0]["source"] == "new"

    def test_preserves_order_of_first_occurrence(self):
        entries = [
            _make_entry(name="x"),
            _make_entry(name="y"),
            _make_entry(name="x", source="override"),
        ]
        result = _dedupe_entries(entries)
        assert [e["name"] for e in result] == ["x", "y"]
        assert result[0]["source"] == "override"

    def test_empty_list(self):
        assert _dedupe_entries([]) == []

    def test_single_entry(self):
        entries = [_make_entry(name="only")]
        result = _dedupe_entries(entries)
        assert len(result) == 1
        assert result[0]["name"] == "only"

    def test_three_duplicates(self):
        entries = [
            _make_entry(name="dup", source="first"),
            _make_entry(name="dup", source="second"),
            _make_entry(name="dup", source="third"),
        ]
        result = _dedupe_entries(entries)
        assert len(result) == 1
        assert result[0]["source"] == "third"


# ── save_plugin_entries / load_plugin_entries ────────────────────────


class TestSaveLoadPluginEntries:
    def test_save_creates_file(self, store_file):
        save_plugin_entries([_make_entry(name="p1")])
        assert store_file.exists()

    def test_save_writes_valid_json(self, store_file):
        save_plugin_entries([_make_entry(name="p1")])
        data = json.loads(store_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "version" in data
        assert "plugins" in data

    def test_save_includes_version(self, store_file):
        save_plugin_entries([])
        data = json.loads(store_file.read_text(encoding="utf-8"))
        assert data["version"] == PLUGIN_STORE_VERSION

    def test_save_normalizes_entries(self, store_file):
        # Entry missing config/source/origin should be normalized
        save_plugin_entries([{"name": "bare"}])
        data = json.loads(store_file.read_text(encoding="utf-8"))
        plugins = data["plugins"]
        assert len(plugins) == 1
        assert plugins[0]["source"] == "plugin"
        assert plugins[0]["config"] == {}

    def test_save_skips_invalid_entries(self, store_file):
        save_plugin_entries([{"name": "good"}, None, {"no_name": True}])
        data = json.loads(store_file.read_text(encoding="utf-8"))
        assert len(data["plugins"]) == 1
        assert data["plugins"][0]["name"] == "good"

    def test_round_trip(self, store_file):
        original = [
            _make_entry(name="alpha", config={"k": "v"}, origin="/some/path"),
            _make_entry(name="beta", enabled=False, source="manifest"),
        ]
        save_plugin_entries(original)
        loaded = load_plugin_entries()
        assert len(loaded) == 2
        assert loaded[0]["name"] == "alpha"
        assert loaded[0]["config"] == {"k": "v"}
        assert loaded[1]["name"] == "beta"
        assert loaded[1]["enabled"] is False

    def test_load_returns_defaults_when_no_file(self, monkeypatch):
        """When the store file does not exist, defaults are returned."""
        # We need to also mock get_default_plugin_entries to avoid yaml dependency
        monkeypatch.setattr(
            "cuvis_ai_ui.settings.plugins.get_default_plugin_entries",
            lambda: [_make_entry(name="default_plugin")],
        )
        loaded = load_plugin_entries()
        assert len(loaded) == 1
        assert loaded[0]["name"] == "default_plugin"

    def test_load_returns_defaults_when_corrupt_file(self, store_file, monkeypatch):
        store_file.write_text("{bad json", encoding="utf-8")
        monkeypatch.setattr(
            "cuvis_ai_ui.settings.plugins.get_default_plugin_entries",
            lambda: [_make_entry(name="fallback")],
        )
        loaded = load_plugin_entries()
        assert len(loaded) == 1
        assert loaded[0]["name"] == "fallback"

    def test_load_handles_top_level_list(self, store_file):
        """Older format might store a bare list instead of {plugins: [...]}."""
        store_file.write_text(
            json.dumps([{"name": "list_entry", "enabled": True}]),
            encoding="utf-8",
        )
        loaded = load_plugin_entries()
        assert len(loaded) == 1
        assert loaded[0]["name"] == "list_entry"

    def test_load_handles_dict_with_plugins_key(self, store_file):
        data = {
            "version": 1,
            "plugins": [{"name": "dict_entry", "enabled": True}],
        }
        store_file.write_text(json.dumps(data), encoding="utf-8")
        loaded = load_plugin_entries()
        assert len(loaded) == 1
        assert loaded[0]["name"] == "dict_entry"

    def test_load_dedupes_entries(self, store_file):
        data = {
            "plugins": [
                {"name": "dup", "source": "first"},
                {"name": "dup", "source": "second"},
            ],
        }
        store_file.write_text(json.dumps(data), encoding="utf-8")
        loaded = load_plugin_entries()
        assert len(loaded) == 1
        assert loaded[0]["source"] == "second"

    def test_load_skips_invalid_entries_in_file(self, store_file):
        data = {
            "plugins": [
                {"name": "valid"},
                None,
                {"no_name": True},
                {"name": "also_valid"},
            ],
        }
        store_file.write_text(json.dumps(data), encoding="utf-8")
        loaded = load_plugin_entries()
        assert [e["name"] for e in loaded] == ["valid", "also_valid"]

    def test_load_returns_defaults_when_non_dict_non_list(self, store_file, monkeypatch):
        """If the JSON root is a string/int/etc., fall back to defaults."""
        store_file.write_text('"just a string"', encoding="utf-8")
        monkeypatch.setattr(
            "cuvis_ai_ui.settings.plugins.get_default_plugin_entries",
            lambda: [],
        )
        loaded = load_plugin_entries()
        assert loaded == []


# ── reset_plugin_entries ─────────────────────────────────────────────


class TestResetPluginEntries:
    def test_reset_returns_defaults(self, monkeypatch):
        monkeypatch.setattr(
            "cuvis_ai_ui.settings.plugins.get_default_plugin_entries",
            lambda: [_make_entry(name="default")],
        )
        result = reset_plugin_entries()
        assert len(result) == 1
        assert result[0]["name"] == "default"

    def test_reset_persists_to_disk(self, store_file, monkeypatch):
        monkeypatch.setattr(
            "cuvis_ai_ui.settings.plugins.get_default_plugin_entries",
            lambda: [_make_entry(name="saved_default")],
        )
        reset_plugin_entries()
        assert store_file.exists()
        data = json.loads(store_file.read_text(encoding="utf-8"))
        assert data["plugins"][0]["name"] == "saved_default"


# ── merge_plugin_entries ─────────────────────────────────────────────


class TestMergePluginEntries:
    def test_no_overlap(self):
        existing = [_make_entry(name="a")]
        updates = [_make_entry(name="b")]
        merged = merge_plugin_entries(existing, updates)
        assert [e["name"] for e in merged] == ["a", "b"]

    def test_update_overrides_existing(self):
        existing = [_make_entry(name="x", source="old")]
        updates = [_make_entry(name="x", source="new")]
        merged = merge_plugin_entries(existing, updates)
        assert len(merged) == 1
        assert merged[0]["source"] == "new"

    def test_new_entries_appended_at_end(self):
        existing = [_make_entry(name="first")]
        updates = [_make_entry(name="second"), _make_entry(name="third")]
        merged = merge_plugin_entries(existing, updates)
        assert [e["name"] for e in merged] == ["first", "second", "third"]

    def test_order_preserved(self):
        existing = [_make_entry(name="a"), _make_entry(name="b"), _make_entry(name="c")]
        updates = [_make_entry(name="b", source="updated")]
        merged = merge_plugin_entries(existing, updates)
        assert [e["name"] for e in merged] == ["a", "b", "c"]
        assert merged[1]["source"] == "updated"

    def test_empty_existing(self):
        merged = merge_plugin_entries([], [_make_entry(name="new")])
        assert len(merged) == 1
        assert merged[0]["name"] == "new"

    def test_empty_updates(self):
        merged = merge_plugin_entries([_make_entry(name="keep")], [])
        assert len(merged) == 1
        assert merged[0]["name"] == "keep"

    def test_both_empty(self):
        assert merge_plugin_entries([], []) == []

    def test_invalid_entries_skipped(self):
        existing = [_make_entry(name="good"), {"no_name": True}]
        updates = [None, _make_entry(name="also_good")]
        merged = merge_plugin_entries(existing, updates)
        names = [e["name"] for e in merged]
        assert "good" in names
        assert "also_good" in names

    def test_multiple_updates_to_same_entry(self):
        existing = [_make_entry(name="a", source="v1")]
        updates = [_make_entry(name="a", source="v2")]
        merged = merge_plugin_entries(existing, updates)
        assert merged[0]["source"] == "v2"


# ── build_manifest ───────────────────────────────────────────────────


class TestBuildManifest:
    def test_basic_manifest(self):
        entries = [_make_entry(name="p1", config={"path": "/abs/path"})]
        manifest = build_manifest(entries)
        assert "plugins" in manifest
        assert "p1" in manifest["plugins"]
        assert manifest["plugins"]["p1"]["path"] == "/abs/path"

    def test_only_enabled_entries_by_default(self):
        entries = [
            _make_entry(name="on", enabled=True),
            _make_entry(name="off", enabled=False),
        ]
        manifest = build_manifest(entries)
        assert "on" in manifest["plugins"]
        assert "off" not in manifest["plugins"]

    def test_enabled_only_false_includes_all(self):
        entries = [
            _make_entry(name="on", enabled=True),
            _make_entry(name="off", enabled=False),
        ]
        manifest = build_manifest(entries, enabled_only=False)
        assert "on" in manifest["plugins"]
        assert "off" in manifest["plugins"]

    def test_resolves_relative_path_with_origin(self):
        entries = [
            _make_entry(
                name="rel",
                config={"path": "subdir/module"},
                origin="/base/dir/catalog.yaml",
            ),
        ]
        manifest = build_manifest(entries)
        expected = str(Path("/base/dir") / "subdir" / "module")
        assert manifest["plugins"]["rel"]["path"] == expected

    def test_absolute_path_not_changed(self):
        abs_path = str(Path("/absolute/path/module"))
        entries = [
            _make_entry(
                name="abs",
                config={"path": abs_path},
                origin="/base/dir/catalog.yaml",
            ),
        ]
        manifest = build_manifest(entries)
        assert manifest["plugins"]["abs"]["path"] == abs_path

    def test_no_origin_leaves_relative_path(self):
        entries = [_make_entry(name="norig", config={"path": "relative/path"})]
        manifest = build_manifest(entries)
        assert manifest["plugins"]["norig"]["path"] == "relative/path"

    def test_removes_empty_provides_list(self):
        entries = [_make_entry(name="prov", config={"provides": []})]
        manifest = build_manifest(entries)
        assert "provides" not in manifest["plugins"]["prov"]

    def test_keeps_non_empty_provides_list(self):
        entries = [_make_entry(name="prov", config={"provides": ["node.Foo"]})]
        manifest = build_manifest(entries)
        assert manifest["plugins"]["prov"]["provides"] == ["node.Foo"]

    def test_empty_entries_produces_empty_manifest(self):
        manifest = build_manifest([])
        assert manifest == {"plugins": {}}

    def test_skips_invalid_entries(self):
        entries = [None, {"no_name": True}, _make_entry(name="ok")]
        manifest = build_manifest(entries)
        assert list(manifest["plugins"].keys()) == ["ok"]

    def test_config_is_copied_not_mutated(self):
        config = {"path": "rel/path", "provides": []}
        origin = "/base/catalog.yaml"
        entries = [_make_entry(name="mut", config=config, origin=origin)]
        build_manifest(entries)
        # Original config should not be mutated
        assert config["path"] == "rel/path"
        assert config["provides"] == []


# ── write_manifest_temp ──────────────────────────────────────────────


class TestWriteManifestTemp:
    def test_creates_file(self):
        manifest = {"plugins": {"p1": {}}}
        path = write_manifest_temp(manifest)
        try:
            assert path.exists()
        finally:
            path.unlink(missing_ok=True)

    def test_file_contains_valid_json(self):
        manifest = {"plugins": {"p1": {"key": "value"}}}
        path = write_manifest_temp(manifest)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data == manifest
        finally:
            path.unlink(missing_ok=True)

    def test_file_has_json_suffix(self):
        manifest = {"plugins": {}}
        path = write_manifest_temp(manifest)
        try:
            assert path.suffix == ".json"
        finally:
            path.unlink(missing_ok=True)

    def test_returns_path_object(self):
        manifest = {"plugins": {}}
        path = write_manifest_temp(manifest)
        try:
            assert isinstance(path, Path)
        finally:
            path.unlink(missing_ok=True)

    def test_empty_manifest(self):
        path = write_manifest_temp({})
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data == {}
        finally:
            path.unlink(missing_ok=True)
