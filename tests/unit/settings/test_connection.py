"""Tests for connection settings persistence."""

import json

import pytest

from cuvis_ai_ui.settings.connection import (
    CONNECTION_STORE_VERSION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    get_default_connection_settings,
    load_connection_settings,
    save_connection_settings,
)


@pytest.fixture(autouse=True)
def _patch_store_path(tmp_path, monkeypatch):
    """Redirect the connection store to a temp directory for every test."""
    store_file = tmp_path / "connection.json"
    monkeypatch.setattr(
        "cuvis_ai_ui.settings.connection._connection_store_path",
        lambda: store_file,
    )
    return store_file


@pytest.fixture
def store_file(tmp_path):
    return tmp_path / "connection.json"


# ── get_default_connection_settings ──────────────────────────────────


class TestGetDefaultConnectionSettings:
    def test_returns_dict(self):
        defaults = get_default_connection_settings()
        assert isinstance(defaults, dict)

    def test_version(self):
        defaults = get_default_connection_settings()
        assert defaults["version"] == CONNECTION_STORE_VERSION

    def test_mode_is_local(self):
        defaults = get_default_connection_settings()
        assert defaults["mode"] == "local"

    def test_host(self):
        defaults = get_default_connection_settings()
        assert defaults["host"] == DEFAULT_HOST

    def test_port(self):
        defaults = get_default_connection_settings()
        assert defaults["port"] == DEFAULT_PORT

    def test_auto_start(self):
        defaults = get_default_connection_settings()
        assert defaults["auto_start"] is True

    def test_expected_keys(self):
        defaults = get_default_connection_settings()
        assert set(defaults.keys()) == {"version", "mode", "host", "port", "auto_start"}

    def test_returns_fresh_dict_each_call(self):
        """Ensure callers cannot mutate the canonical defaults."""
        d1 = get_default_connection_settings()
        d2 = get_default_connection_settings()
        assert d1 is not d2
        assert d1 == d2


# ── load_connection_settings ─────────────────────────────────────────


class TestLoadConnectionSettings:
    def test_returns_defaults_when_no_file(self):
        """When the store file does not exist, defaults are returned."""
        settings = load_connection_settings()
        assert settings == get_default_connection_settings()

    def test_returns_defaults_when_file_is_empty(self, store_file):
        store_file.write_text("", encoding="utf-8")
        settings = load_connection_settings()
        assert settings == get_default_connection_settings()

    def test_returns_defaults_when_file_is_invalid_json(self, store_file):
        store_file.write_text("{bad json", encoding="utf-8")
        settings = load_connection_settings()
        assert settings == get_default_connection_settings()

    def test_returns_defaults_when_file_contains_json_list(self, store_file):
        store_file.write_text("[]", encoding="utf-8")
        settings = load_connection_settings()
        assert settings == get_default_connection_settings()

    def test_returns_defaults_when_file_contains_json_string(self, store_file):
        store_file.write_text('"hello"', encoding="utf-8")
        settings = load_connection_settings()
        assert settings == get_default_connection_settings()

    # ── mode validation ──────────────────────────────────────────────

    def test_loads_valid_mode_local(self, store_file):
        store_file.write_text(json.dumps({"mode": "local"}), encoding="utf-8")
        assert load_connection_settings()["mode"] == "local"

    def test_loads_valid_mode_remote(self, store_file):
        store_file.write_text(json.dumps({"mode": "remote"}), encoding="utf-8")
        assert load_connection_settings()["mode"] == "remote"

    def test_ignores_invalid_mode(self, store_file):
        store_file.write_text(json.dumps({"mode": "cloud"}), encoding="utf-8")
        assert load_connection_settings()["mode"] == "local"

    def test_ignores_non_string_mode(self, store_file):
        store_file.write_text(json.dumps({"mode": 42}), encoding="utf-8")
        assert load_connection_settings()["mode"] == "local"

    # ── host validation ──────────────────────────────────────────────

    def test_loads_valid_host(self, store_file):
        store_file.write_text(json.dumps({"host": "10.0.0.1"}), encoding="utf-8")
        assert load_connection_settings()["host"] == "10.0.0.1"

    def test_ignores_empty_host(self, store_file):
        store_file.write_text(json.dumps({"host": ""}), encoding="utf-8")
        assert load_connection_settings()["host"] == DEFAULT_HOST

    def test_ignores_non_string_host(self, store_file):
        store_file.write_text(json.dumps({"host": 123}), encoding="utf-8")
        assert load_connection_settings()["host"] == DEFAULT_HOST

    # ── port validation ──────────────────────────────────────────────

    def test_loads_valid_port(self, store_file):
        store_file.write_text(json.dumps({"port": 8080}), encoding="utf-8")
        assert load_connection_settings()["port"] == 8080

    def test_loads_port_min_boundary(self, store_file):
        store_file.write_text(json.dumps({"port": 1}), encoding="utf-8")
        assert load_connection_settings()["port"] == 1

    def test_loads_port_max_boundary(self, store_file):
        store_file.write_text(json.dumps({"port": 65535}), encoding="utf-8")
        assert load_connection_settings()["port"] == 65535

    def test_ignores_port_zero(self, store_file):
        store_file.write_text(json.dumps({"port": 0}), encoding="utf-8")
        assert load_connection_settings()["port"] == DEFAULT_PORT

    def test_ignores_port_negative(self, store_file):
        store_file.write_text(json.dumps({"port": -1}), encoding="utf-8")
        assert load_connection_settings()["port"] == DEFAULT_PORT

    def test_ignores_port_too_large(self, store_file):
        store_file.write_text(json.dumps({"port": 70000}), encoding="utf-8")
        assert load_connection_settings()["port"] == DEFAULT_PORT

    def test_ignores_non_int_port(self, store_file):
        store_file.write_text(json.dumps({"port": "8080"}), encoding="utf-8")
        assert load_connection_settings()["port"] == DEFAULT_PORT

    def test_ignores_float_port(self, store_file):
        """JSON floats like 8080.0 are not int in Python, so they should be rejected."""
        store_file.write_text(json.dumps({"port": 8080.5}), encoding="utf-8")
        assert load_connection_settings()["port"] == DEFAULT_PORT

    # ── auto_start validation ────────────────────────────────────────

    def test_loads_auto_start_true(self, store_file):
        store_file.write_text(json.dumps({"auto_start": True}), encoding="utf-8")
        assert load_connection_settings()["auto_start"] is True

    def test_loads_auto_start_false(self, store_file):
        store_file.write_text(json.dumps({"auto_start": False}), encoding="utf-8")
        assert load_connection_settings()["auto_start"] is False

    def test_ignores_non_bool_auto_start(self, store_file):
        store_file.write_text(json.dumps({"auto_start": 1}), encoding="utf-8")
        # Default auto_start is True, and int(1) is not bool
        assert load_connection_settings()["auto_start"] is True

    # ── merging behavior ─────────────────────────────────────────────

    def test_merges_partial_file_over_defaults(self, store_file):
        """Only recognized, valid keys override defaults; others keep defaults."""
        store_file.write_text(
            json.dumps({"mode": "remote", "port": 9999}),
            encoding="utf-8",
        )
        settings = load_connection_settings()
        assert settings["mode"] == "remote"
        assert settings["port"] == 9999
        # Remaining keys should be defaults
        assert settings["host"] == DEFAULT_HOST
        assert settings["auto_start"] is True
        assert settings["version"] == CONNECTION_STORE_VERSION

    def test_ignores_unknown_keys(self, store_file):
        store_file.write_text(json.dumps({"unknown_key": "value"}), encoding="utf-8")
        settings = load_connection_settings()
        assert "unknown_key" not in settings
        assert settings == get_default_connection_settings()

    def test_all_valid_fields_loaded(self, store_file):
        data = {
            "mode": "remote",
            "host": "192.168.1.1",
            "port": 12345,
            "auto_start": False,
        }
        store_file.write_text(json.dumps(data), encoding="utf-8")
        settings = load_connection_settings()
        assert settings["mode"] == "remote"
        assert settings["host"] == "192.168.1.1"
        assert settings["port"] == 12345
        assert settings["auto_start"] is False


# ── save_connection_settings ─────────────────────────────────────────


class TestSaveConnectionSettings:
    def test_creates_file(self, store_file):
        save_connection_settings(get_default_connection_settings())
        assert store_file.exists()

    def test_file_is_valid_json(self, store_file):
        save_connection_settings(get_default_connection_settings())
        data = json.loads(store_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_saved_content_matches_input(self, store_file):
        settings = {
            "mode": "remote",
            "host": "10.0.0.5",
            "port": 9090,
            "auto_start": False,
        }
        save_connection_settings(settings)
        data = json.loads(store_file.read_text(encoding="utf-8"))
        assert data["version"] == CONNECTION_STORE_VERSION
        assert data["mode"] == "remote"
        assert data["host"] == "10.0.0.5"
        assert data["port"] == 9090
        assert data["auto_start"] is False

    def test_defaults_used_for_missing_keys(self, store_file):
        save_connection_settings({})
        data = json.loads(store_file.read_text(encoding="utf-8"))
        assert data["mode"] == "local"
        assert data["host"] == DEFAULT_HOST
        assert data["port"] == DEFAULT_PORT
        assert data["auto_start"] is True

    def test_creates_parent_directories(self, tmp_path, monkeypatch):
        nested = tmp_path / "deep" / "nested" / "connection.json"
        monkeypatch.setattr(
            "cuvis_ai_ui.settings.connection._connection_store_path",
            lambda: nested,
        )
        save_connection_settings(get_default_connection_settings())
        assert nested.exists()

    def test_overwrites_existing_file(self, store_file):
        save_connection_settings({"mode": "local", "port": 1111})
        save_connection_settings({"mode": "remote", "port": 2222})
        data = json.loads(store_file.read_text(encoding="utf-8"))
        assert data["mode"] == "remote"
        assert data["port"] == 2222


# ── round-trip ───────────────────────────────────────────────────────


class TestRoundTrip:
    def test_save_then_load_preserves_settings(self):
        settings = {
            "mode": "remote",
            "host": "myserver.local",
            "port": 44444,
            "auto_start": False,
        }
        save_connection_settings(settings)
        loaded = load_connection_settings()
        assert loaded["mode"] == "remote"
        assert loaded["host"] == "myserver.local"
        assert loaded["port"] == 44444
        assert loaded["auto_start"] is False
        assert loaded["version"] == CONNECTION_STORE_VERSION

    def test_save_defaults_then_load_returns_defaults(self):
        defaults = get_default_connection_settings()
        save_connection_settings(defaults)
        loaded = load_connection_settings()
        assert loaded == defaults

    def test_multiple_round_trips(self):
        for port in (1000, 2000, 3000):
            save_connection_settings({"port": port})
            loaded = load_connection_settings()
            assert loaded["port"] == port
