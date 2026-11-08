"""Pipeline folders, launch targets and plugin registration."""

import json
import threading
from unittest.mock import Mock, call

import pytest

from cuvis_ai_ui.grpc.client import OperationCancelled
from cuvis_ai_ui.workspace import (
    PluginRegistration,
    list_pipelines,
    plugin_dirs_for,
    register_plugins,
    resolve_launch_target,
)


def _touch(path, text="nodes: []\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _entry(name, enabled=True):
    return {
        "name": name,
        "enabled": enabled,
        "source": "plugin",
        "config": {"repo": f"https://example.com/{name}.git", "tag": "v1.0.0"},
        "origin": None,
    }


class TestListPipelines:
    def test_lists_yaml_files_sorted_by_name(self, tmp_path):
        _touch(tmp_path / "b.yaml")
        _touch(tmp_path / "A.yml")
        _touch(tmp_path / "c.YAML")
        assert [p.name for p in list_pipelines(tmp_path)] == ["A.yml", "b.yaml", "c.YAML"]

    def test_skips_other_files_and_subfolders(self, tmp_path):
        _touch(tmp_path / "pipe.yaml")
        _touch(tmp_path / "pipe.png", "")
        _touch(tmp_path / "README.md", "")
        _touch(tmp_path / "plugins" / "sam3.yaml")
        assert [p.name for p in list_pipelines(tmp_path)] == ["pipe.yaml"]

    def test_empty_folder(self, tmp_path):
        assert list_pipelines(tmp_path) == []


class TestResolveLaunchTarget:
    def test_no_path(self):
        assert resolve_launch_target(None) == (None, None)

    def test_folder_opens_its_first_pipeline(self, tmp_path):
        _touch(tmp_path / "b.yaml")
        first = _touch(tmp_path / "a.yaml")
        assert resolve_launch_target(tmp_path) == (tmp_path, first)

    def test_folder_without_pipelines(self, tmp_path):
        assert resolve_launch_target(tmp_path) == (tmp_path, None)

    def test_file_opens_alone(self, tmp_path):
        pipe = _touch(tmp_path / "a.yaml")
        assert resolve_launch_target(pipe) == (None, pipe)

    def test_relative_paths_come_back_absolute(self, tmp_path, monkeypatch):
        """The window compares the open file with absolute browser and Save As
        paths, so a relative cuvis-ui PATH is made absolute here."""
        (tmp_path / "pipes").mkdir()
        (tmp_path / "pipes" / "a.yaml").write_text("nodes: []\n", encoding="utf-8")
        (tmp_path / "one.yaml").write_text("nodes: []\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        folder, first = resolve_launch_target("pipes")
        assert folder == (tmp_path / "pipes").absolute()
        assert first == (tmp_path / "pipes" / "a.yaml").absolute()
        assert resolve_launch_target("one.yaml") == (None, (tmp_path / "one.yaml").absolute())

    def test_missing_path_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_launch_target(tmp_path / "nope")


class TestPluginDirsFor:
    def test_cli_dirs_then_the_folder_plugins_dir(self, tmp_path):
        (tmp_path / "pipes" / "plugins").mkdir(parents=True)
        cli = [tmp_path / "x", tmp_path / "y"]
        assert plugin_dirs_for(cli, tmp_path / "pipes") == [*cli, tmp_path / "pipes" / "plugins"]

    def test_folder_without_plugins_dir(self, tmp_path):
        assert plugin_dirs_for([tmp_path / "x"], tmp_path) == [tmp_path / "x"]

    def test_no_folder(self, tmp_path):
        assert plugin_dirs_for([tmp_path / "x"], None) == [tmp_path / "x"]


class TestRegisterPlugins:
    @pytest.fixture
    def client(self, mock_grpc_client):
        sent = {}

        def load_plugins(path, stop=None):
            sent["path"] = path
            sent["manifest"] = json.loads(open(path, encoding="utf-8").read())
            return {"loaded_plugins": ["a"], "failed_plugins": ["c"]}

        mock_grpc_client.load_plugins.side_effect = load_plugins
        mock_grpc_client.list_available_nodes.return_value = [{"class_name": "N"}]
        mock_grpc_client.sent = sent
        return mock_grpc_client

    def test_registers_enabled_plugins_and_lists_nodes(self, client):
        result = register_plugins(client, [_entry("a"), _entry("b", enabled=False), _entry("c")])

        assert [m["name"] for m in client.sent["manifest"]] == ["a", "c"]
        assert not client.sent["path"].exists()
        assert result.loaded == ["a"]
        assert result.failed == ["c"]
        assert result.nodes == [{"class_name": "N", "input_specs": [], "output_specs": []}]

    def test_fresh_session_replaces_the_session_before_loading(self, client):
        calls = Mock()
        calls.attach_mock(client.close_session, "close_session")
        calls.attach_mock(client.create_session, "create_session")
        calls.attach_mock(client.load_plugins, "load_plugins")

        register_plugins(client, [_entry("a")], fresh_session=True)

        assert [c[0] for c in calls.mock_calls] == [
            "close_session",
            "create_session",
            "load_plugins",
        ]

    def test_a_manifest_that_cannot_be_written_keeps_the_old_session(self, client, monkeypatch):
        """The plugin set is written out before the session is replaced, so a
        manifest that fails there leaves the working session and its catalog."""
        monkeypatch.setattr(
            "cuvis_ai_ui.workspace.write_manifest_temp", Mock(side_effect=TypeError("bad value"))
        )
        with pytest.raises(TypeError):
            register_plugins(client, [_entry("a")], fresh_session=True)
        client.close_session.assert_not_called()
        client.create_session.assert_not_called()

    def test_a_failed_session_close_is_retried_once(self, client):
        client.close_session.side_effect = [False, True]
        register_plugins(client, [_entry("a")], fresh_session=True)
        assert client.close_session.call_count == 2
        client.create_session.assert_called_once()

    @pytest.mark.parametrize("closes", [[False], [False, False]])
    def test_a_cancel_during_a_failed_close_keeps_the_old_session(self, client, closes):
        """Cancel lands while a CloseSession stalls and fails: no retry and no new
        session, so the client keeps the session it has; nothing is registered."""
        stop = threading.Event()
        results = iter(closes)

        def close():
            if len(closes) == 1 or client.close_session.call_count == 2:
                stop.set()
            return next(results)

        client.close_session.side_effect = close
        with pytest.raises(OperationCancelled):
            register_plugins(client, [_entry("a")], fresh_session=True, stop=stop)
        assert client.close_session.call_count == len(closes)
        client.create_session.assert_not_called()
        client.load_plugins.assert_not_called()
        client.list_available_nodes.assert_not_called()

    def test_a_cancel_after_the_old_session_closed_still_opens_the_new_one(self, client):
        """With the old session closed, the new one is opened anyway so the client
        is never left without a session; the cancel stops before the node list."""
        stop = threading.Event()

        def close():
            stop.set()
            return True

        client.close_session.side_effect = close
        with pytest.raises(OperationCancelled):
            register_plugins(client, [_entry("a")], fresh_session=True, stop=stop)
        client.create_session.assert_called_once()
        client.list_available_nodes.assert_not_called()

    def test_a_session_that_will_not_close_is_still_replaced(self, client):
        client.close_session.return_value = False
        result = register_plugins(client, [_entry("a")], fresh_session=True)
        assert client.close_session.call_count == 2
        client.create_session.assert_called_once()
        assert result.loaded == ["a"]

    def test_keeps_the_session_by_default(self, client):
        register_plugins(client, [_entry("a")])
        client.close_session.assert_not_called()
        client.create_session.assert_not_called()

    def test_no_enabled_plugins_still_lists_nodes(self, client):
        result = register_plugins(client, [_entry("a", enabled=False)])
        client.load_plugins.assert_not_called()
        assert client.list_available_nodes.call_args_list == [call()]
        assert result.loaded == [] and result.failed == []

    def test_a_cancel_before_it_starts_keeps_the_session(self, client):
        stop = threading.Event()
        stop.set()
        with pytest.raises(OperationCancelled):
            register_plugins(client, [_entry("a")], fresh_session=True, stop=stop)
        client.close_session.assert_not_called()
        client.load_plugins.assert_not_called()

    def test_the_stop_event_reaches_load_plugins(self, client):
        stop = threading.Event()
        register_plugins(client, [_entry("a")], stop=stop)
        assert client.load_plugins.call_args.kwargs == {"stop": stop}

    def test_a_cancel_during_loading_skips_listing_and_removes_the_manifest(self, client):
        stop = threading.Event()
        sent = client.sent
        loader = client.load_plugins.side_effect

        def load_then_cancel(path, stop=None):
            result = loader(path, stop)
            cancel.set()
            return result

        cancel = stop

        client.load_plugins.side_effect = load_then_cancel
        with pytest.raises(OperationCancelled):
            register_plugins(client, [_entry("a")], stop=stop)
        client.list_available_nodes.assert_not_called()
        assert not sent["path"].exists()


class TestPluginRegistrationStatus:
    def test_counts_nodes_and_plugins(self):
        result = PluginRegistration(nodes=[{}] * 3, loaded=["a", "b"], failed=[])
        assert result.status_text() == "2 plugins, 3 nodes"

    def test_names_failed_plugins(self):
        result = PluginRegistration(nodes=[{}], loaded=["a"], failed=["x", "y"])
        assert result.status_text() == "1 plugin, 1 node; failed to load: x, y"
