"""Tests for plugin settings persistence."""

import json
from pathlib import Path

import pytest

from cuvis_ai_ui.settings.plugins import (
    PLUGIN_STORE_VERSION,
    _coerce_capabilities,
    _dedupe_entries,
    _load_manifest_entries,
    _migrate_entry,
    _normalize_entry,
    _resolve_local_path,
    build_manifest,
    load_plugin_entries,
    load_plugin_entries_from_directory,
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


# ── store migration (v1 → v2) ────────────────────────────────────────


class TestStoreMigration:
    def test_store_version_is_2(self):
        assert PLUGIN_STORE_VERSION == 2

    def test_migrate_entry_renames_provides_to_capabilities(self):
        entry = {
            "name": "p",
            "enabled": True,
            "source": "git",
            "config": {"repo": "x", "tag": "v1", "provides": [{"class_name": "a.b.C"}]},
        }
        migrated = _migrate_entry(entry)
        assert "provides" not in migrated["config"]
        assert migrated["config"]["capabilities"] == [{"class_name": "a.b.C"}]
        # Other config keys are preserved.
        assert migrated["config"]["repo"] == "x"
        assert migrated["config"]["tag"] == "v1"

    def test_migrate_entry_idempotent(self):
        entry = {
            "name": "p",
            "config": {"capabilities": [{"class_name": "a.b.C"}]},
        }
        once = _migrate_entry(entry)
        twice = _migrate_entry(once)
        assert once == twice
        assert once["config"]["capabilities"] == [{"class_name": "a.b.C"}]

    def test_migrate_entry_no_provides_unchanged(self):
        entry = {"name": "p", "config": {"path": "/p"}}
        assert _migrate_entry(entry) == entry

    def test_old_plugins_json_v1_migrated_on_load(self, store_file):
        # A persisted v1 store with config.provides is rewritten to
        # config.capabilities on load.
        data = {
            "version": 1,
            "plugins": [
                {
                    "name": "legacy",
                    "enabled": True,
                    "source": "git",
                    "config": {
                        "repo": "https://example.com/legacy.git",
                        "tag": "v0.1.0",
                        "provides": [{"class_name": "legacy.node.Foo"}],
                    },
                }
            ],
        }
        store_file.write_text(json.dumps(data), encoding="utf-8")

        loaded = load_plugin_entries()
        assert len(loaded) == 1
        config = loaded[0]["config"]
        assert "provides" not in config
        assert config["capabilities"] == [{"class_name": "legacy.node.Foo"}]

    def test_load_migration_is_idempotent_round_trip(self, store_file):
        # v1 store loads → migrated → save (stamps v2) → reload yields the same
        # capabilities and a v2 version stamp.
        data = {
            "version": 1,
            "plugins": [
                {
                    "name": "legacy",
                    "config": {"path": "/p", "provides": ["legacy.node.Foo"]},
                }
            ],
        }
        store_file.write_text(json.dumps(data), encoding="utf-8")

        first = load_plugin_entries()
        save_plugin_entries(first)
        on_disk = json.loads(store_file.read_text(encoding="utf-8"))
        assert on_disk["version"] == 2

        second = load_plugin_entries()
        assert second[0]["config"]["capabilities"] == ["legacy.node.Foo"]
        assert "provides" not in second[0]["config"]

    def test_migration_prefers_existing_capabilities(self):
        # If both keys are somehow present, capabilities wins and provides drops.
        entry = {
            "name": "p",
            "config": {
                "capabilities": [{"class_name": "new.Node"}],
                "provides": [{"class_name": "old.Node"}],
            },
        }
        migrated = _migrate_entry(entry)
        assert "provides" not in migrated["config"]
        assert migrated["config"]["capabilities"] == [{"class_name": "new.Node"}]


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


def _manifest_by_name(manifest: list[dict], name: str) -> dict:
    """Return the single bare manifest with the given name (or raise)."""
    matches = [m for m in manifest if m.get("name") == name]
    assert len(matches) == 1, f"expected exactly one {name!r}, got {matches}"
    return matches[0]


class TestBuildManifest:
    def test_returns_list_of_bare_manifests(self):
        entries = [_make_entry(name="p1", config={"path": "/abs/path"})]
        manifest = build_manifest(entries)
        assert isinstance(manifest, list)
        assert manifest == [{"name": "p1", "path": "/abs/path"}]

    def test_basic_manifest(self):
        entries = [_make_entry(name="p1", config={"path": "/abs/path"})]
        manifest = build_manifest(entries)
        p1 = _manifest_by_name(manifest, "p1")
        assert p1["path"] == "/abs/path"

    def test_only_enabled_entries_by_default(self):
        entries = [
            _make_entry(name="on", enabled=True),
            _make_entry(name="off", enabled=False),
        ]
        manifest = build_manifest(entries)
        names = {m["name"] for m in manifest}
        assert "on" in names
        assert "off" not in names

    def test_enabled_only_false_includes_all(self):
        entries = [
            _make_entry(name="on", enabled=True),
            _make_entry(name="off", enabled=False),
        ]
        manifest = build_manifest(entries, enabled_only=False)
        names = {m["name"] for m in manifest}
        assert "on" in names
        assert "off" in names

    def test_resolves_relative_path_with_origin(self, tmp_path):
        origin = tmp_path / "catalog.yaml"
        entries = [
            _make_entry(
                name="rel",
                config={"path": "subdir/module"},
                origin=str(origin),
            ),
        ]
        manifest = build_manifest(entries)
        expected = str((tmp_path / "subdir" / "module").resolve())
        assert _manifest_by_name(manifest, "rel")["path"] == expected

    def test_resolves_dotdot_path_with_origin(self, tmp_path):
        # Regression: `path: "../.."` in a YAML must resolve against the
        # YAML's dir, not the server's CWD, before crossing gRPC.
        nested = tmp_path / "configs" / "plugins"
        nested.mkdir(parents=True)
        origin = nested / "builtin.yaml"
        entries = [
            _make_entry(
                name="builtin",
                config={"path": "../.."},
                origin=str(origin),
            ),
        ]
        manifest = build_manifest(entries)
        assert _manifest_by_name(manifest, "builtin")["path"] == str(tmp_path.resolve())

    def test_absolute_path_not_changed(self, tmp_path):
        abs_path = str((tmp_path / "absolute" / "module").resolve())
        entries = [
            _make_entry(
                name="abs",
                config={"path": abs_path},
                origin=str(tmp_path / "catalog.yaml"),
            ),
        ]
        manifest = build_manifest(entries)
        assert _manifest_by_name(manifest, "abs")["path"] == abs_path

    def test_no_origin_leaves_relative_path(self):
        entries = [_make_entry(name="norig", config={"path": "relative/path"})]
        manifest = build_manifest(entries)
        assert _manifest_by_name(manifest, "norig")["path"] == "relative/path"

    def test_removes_empty_capabilities_list(self):
        entries = [_make_entry(name="cap", config={"capabilities": []})]
        manifest = build_manifest(entries)
        assert "capabilities" not in _manifest_by_name(manifest, "cap")

    def test_coerces_bare_string_capabilities_to_entries(self):
        # The manifest schema now requires PluginCapabilityEntry objects; bare
        # class strings must be wrapped into {class_name: ...} dicts.
        entries = [_make_entry(name="cap", config={"capabilities": ["pkg.node.Foo"]})]
        manifest = build_manifest(entries)
        assert _manifest_by_name(manifest, "cap")["capabilities"] == [
            {"class_name": "pkg.node.Foo"}
        ]

    def test_leaves_dict_capabilities_untouched(self):
        entry_dict = {"class_name": "pkg.node.Foo", "category": "transform"}
        entries = [_make_entry(name="cap", config={"capabilities": [entry_dict]})]
        manifest = build_manifest(entries)
        assert _manifest_by_name(manifest, "cap")["capabilities"] == [entry_dict]

    def test_capabilities_entries_validate_as_capability_entry(self):
        from cuvis_ai_schemas.plugin import PluginCapabilityEntry

        entries = [_make_entry(name="cap", config={"capabilities": ["pkg.mod.Node"]})]
        manifest = build_manifest(entries)
        for raw in _manifest_by_name(manifest, "cap")["capabilities"]:
            PluginCapabilityEntry(**raw)  # raises if the wrapped shape is invalid

    def test_empty_entries_produces_empty_list(self):
        manifest = build_manifest([])
        assert manifest == []

    def test_skips_invalid_entries(self):
        entries = [None, {"no_name": True}, _make_entry(name="ok")]
        manifest = build_manifest(entries)
        assert [m["name"] for m in manifest] == ["ok"]

    def test_config_is_copied_not_mutated(self):
        config = {"path": "rel/path", "capabilities": []}
        origin = "/base/catalog.yaml"
        entries = [_make_entry(name="mut", config=config, origin=origin)]
        build_manifest(entries)
        # Original config should not be mutated
        assert config["path"] == "rel/path"
        assert config["capabilities"] == []


# ── _coerce_capabilities ─────────────────────────────────────────────


class TestCoerceCapabilities:
    def test_wraps_string_entries(self):
        config = {"capabilities": ["a.b.C", "a.b.D"]}
        result = _coerce_capabilities(config)
        assert result["capabilities"] == [{"class_name": "a.b.C"}, {"class_name": "a.b.D"}]

    def test_leaves_dict_entries(self):
        config = {"capabilities": [{"class_name": "a.b.C", "category": "sink"}]}
        result = _coerce_capabilities(config)
        assert result["capabilities"] == [{"class_name": "a.b.C", "category": "sink"}]

    def test_mixed_entries(self):
        config = {"capabilities": ["a.b.C", {"class_name": "a.b.D"}]}
        result = _coerce_capabilities(config)
        assert result["capabilities"] == [{"class_name": "a.b.C"}, {"class_name": "a.b.D"}]

    def test_idempotent(self):
        once = _coerce_capabilities({"capabilities": ["a.b.C"]})
        twice = _coerce_capabilities(once)
        assert once["capabilities"] == twice["capabilities"] == [{"class_name": "a.b.C"}]

    def test_no_capabilities_returns_same_object(self):
        config = {"repo": "x", "tag": "v1"}
        assert _coerce_capabilities(config) is config

    def test_non_list_capabilities_returns_same_object(self):
        config = {"capabilities": "not-a-list"}
        assert _coerce_capabilities(config) is config

    def test_all_dict_entries_returns_same_object(self):
        # Nothing to wrap → original object returned unchanged (idempotent fast path).
        config = {"capabilities": [{"class_name": "a.b.C"}]}
        assert _coerce_capabilities(config) is config

    def test_does_not_mutate_input(self):
        config = {"capabilities": ["a.b.C"]}
        _coerce_capabilities(config)
        assert config["capabilities"] == ["a.b.C"]


# ── _resolve_local_path ──────────────────────────────────────────────


class TestResolveLocalPath:
    def test_relative_path_resolved_against_manifest_dir(self, tmp_path):
        config = {"path": "../.."}
        manifest_dir = tmp_path / "configs" / "plugins"
        manifest_dir.mkdir(parents=True)
        resolved = _resolve_local_path(config, manifest_dir)
        assert resolved["path"] == str(tmp_path.resolve())

    def test_absolute_path_passes_through_unchanged(self, tmp_path):
        abs_path = str((tmp_path / "plugin_dir").resolve())
        config = {"path": abs_path, "capabilities": ["a.b.C"]}
        resolved = _resolve_local_path(config, tmp_path / "elsewhere")
        assert resolved["path"] == abs_path
        assert resolved["capabilities"] == ["a.b.C"]

    def test_missing_path_returns_config_unchanged(self, tmp_path):
        config = {"repo": "git@example.com:org/plugin.git", "tag": "v1"}
        resolved = _resolve_local_path(config, tmp_path)
        assert resolved == config

    def test_non_string_path_returns_config_unchanged(self, tmp_path):
        config = {"path": 123}
        resolved = _resolve_local_path(config, tmp_path)
        assert resolved == config

    def test_input_config_not_mutated_when_resolving(self, tmp_path):
        config = {"path": "./sub"}
        _resolve_local_path(config, tmp_path)
        assert config["path"] == "./sub"

    def test_input_config_returned_as_is_when_not_applicable(self, tmp_path):
        # When there's nothing to resolve, the helper may return the same
        # object (no need to copy). Callers should not rely on identity.
        config = {"repo": "x"}
        resolved = _resolve_local_path(config, tmp_path)
        assert resolved == config


# ── write_manifest_temp ──────────────────────────────────────────────


class TestWriteManifestTemp:
    def test_creates_file(self):
        manifest = [{"name": "p1"}]
        path = write_manifest_temp(manifest)
        try:
            assert path.exists()
        finally:
            path.unlink(missing_ok=True)

    def test_file_contains_valid_json_list(self):
        manifest = [{"name": "p1", "key": "value"}]
        path = write_manifest_temp(manifest)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data == manifest
            assert isinstance(data, list)
        finally:
            path.unlink(missing_ok=True)

    def test_file_has_json_suffix(self):
        path = write_manifest_temp([])
        try:
            assert path.suffix == ".json"
        finally:
            path.unlink(missing_ok=True)

    def test_returns_path_object(self):
        path = write_manifest_temp([])
        try:
            assert isinstance(path, Path)
        finally:
            path.unlink(missing_ok=True)

    def test_empty_manifest(self):
        path = write_manifest_temp([])
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data == []
        finally:
            path.unlink(missing_ok=True)


# ── _load_manifest_entries ──────────────────────────────────────────


class TestLoadManifestEntries:
    def test_valid_manifest(self, tmp_path):
        manifest = tmp_path / "my_plugin.yaml"
        manifest.write_text(
            "name: my_plugin\npath: /some/path\ncapabilities:\n  - my_plugin.node.Foo\n",
            encoding="utf-8",
        )
        entries = _load_manifest_entries(manifest)
        assert len(entries) == 1
        assert entries[0]["name"] == "my_plugin"
        assert entries[0]["config"]["path"] == "/some/path"
        # name is stored only on the entry, not duplicated into config.
        assert "name" not in entries[0]["config"]
        assert entries[0]["config"]["capabilities"] == ["my_plugin.node.Foo"]
        assert entries[0]["origin"] == str(manifest)

    def test_one_file_is_one_plugin(self, tmp_path):
        # Even a git-sourced manifest is a single bare plugin per file.
        manifest = tmp_path / "alpha.yaml"
        manifest.write_text(
            "name: alpha\nrepo: https://example.com/a.git\ntag: v1\ncapabilities:\n  - a.b.C\n",
            encoding="utf-8",
        )
        entries = _load_manifest_entries(manifest)
        assert len(entries) == 1
        assert entries[0]["name"] == "alpha"
        assert entries[0]["config"]["repo"] == "https://example.com/a.git"
        assert entries[0]["config"]["tag"] == "v1"

    def test_nonexistent_file(self, tmp_path):
        entries = _load_manifest_entries(tmp_path / "missing.yaml")
        assert entries == []

    def test_invalid_yaml(self, tmp_path):
        manifest = tmp_path / "bad.yaml"
        manifest.write_text("{bad yaml: [", encoding="utf-8")
        entries = _load_manifest_entries(manifest)
        assert entries == []

    def test_empty_file(self, tmp_path):
        manifest = tmp_path / "empty.yaml"
        manifest.write_text("", encoding="utf-8")
        entries = _load_manifest_entries(manifest)
        assert entries == []

    def test_no_name_key(self, tmp_path):
        manifest = tmp_path / "noname.yaml"
        manifest.write_text("something_else: true\n", encoding="utf-8")
        entries = _load_manifest_entries(manifest)
        assert entries == []

    def test_old_plugins_wrapper_shape_is_skipped(self, tmp_path):
        # An old multi-plugin file has no top-level string `name`, so it is
        # skipped rather than mis-parsed.
        manifest = tmp_path / "old.yaml"
        manifest.write_text("plugins:\n  my_plugin:\n    path: /p\n", encoding="utf-8")
        entries = _load_manifest_entries(manifest)
        assert entries == []

    def test_entries_have_correct_defaults(self, tmp_path):
        manifest = tmp_path / "test_plugin.yaml"
        manifest.write_text(
            "name: test_plugin\npath: /p\ncapabilities:\n  - p.q.R\n",
            encoding="utf-8",
        )
        entries = _load_manifest_entries(manifest)
        entry = entries[0]
        assert entry["enabled"] is True
        assert entry["source"] == "manifest"


# ── load_plugin_entries_from_directory ──────────────────────────────


class TestLoadPluginEntriesFromDirectory:
    def test_loads_multiple_manifests(self, tmp_path):
        (tmp_path / "a.yaml").write_text("name: plugin_a\npath: /a\n", encoding="utf-8")
        (tmp_path / "b.yaml").write_text("name: plugin_b\npath: /b\n", encoding="utf-8")
        entries = load_plugin_entries_from_directory(tmp_path)
        assert len(entries) == 2
        assert {e["name"] for e in entries} == {"plugin_a", "plugin_b"}

    def test_deduplicates_across_manifests(self, tmp_path):
        (tmp_path / "a.yaml").write_text("name: dup\npath: /first\n", encoding="utf-8")
        (tmp_path / "b.yaml").write_text("name: dup\npath: /second\n", encoding="utf-8")
        entries = load_plugin_entries_from_directory(tmp_path)
        assert len(entries) == 1
        # b.yaml comes after a.yaml alphabetically, so it wins
        assert entries[0]["config"]["path"] == "/second"

    def test_nonexistent_directory(self, tmp_path):
        entries = load_plugin_entries_from_directory(tmp_path / "missing")
        assert entries == []

    def test_empty_directory(self, tmp_path):
        entries = load_plugin_entries_from_directory(tmp_path)
        assert entries == []

    def test_ignores_non_yaml_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("not a manifest", encoding="utf-8")
        (tmp_path / "data.json").write_text('{"name": "x"}', encoding="utf-8")
        (tmp_path / "real.yaml").write_text("name: real\npath: /r\n", encoding="utf-8")
        entries = load_plugin_entries_from_directory(tmp_path)
        assert len(entries) == 1
        assert entries[0]["name"] == "real"

    def test_skips_invalid_yaml_files(self, tmp_path):
        (tmp_path / "bad.yaml").write_text("{bad yaml: [", encoding="utf-8")
        (tmp_path / "good.yaml").write_text("name: good\npath: /g\n", encoding="utf-8")
        entries = load_plugin_entries_from_directory(tmp_path)
        assert len(entries) == 1
        assert entries[0]["name"] == "good"

    def test_origin_set_per_manifest(self, tmp_path):
        (tmp_path / "x.yaml").write_text("name: px\npath: /x\n", encoding="utf-8")
        (tmp_path / "y.yaml").write_text("name: py\npath: /y\n", encoding="utf-8")
        entries = load_plugin_entries_from_directory(tmp_path)
        origins = {e["name"]: e["origin"] for e in entries}
        assert origins["px"] == str(tmp_path / "x.yaml")
        assert origins["py"] == str(tmp_path / "y.yaml")
