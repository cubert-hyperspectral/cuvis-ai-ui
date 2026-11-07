"""cuvis-ui wiring in main(): what the command line opens and how plugin refreshes land."""

from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QMessageBox

from cuvis_ai_ui import main as main_module
from cuvis_ai_ui.grpc.client import CuvisAIClient
from cuvis_ai_ui.workspace import PluginRegistration

PIPELINE = """metadata:
  name: {name}
plugins: [p]
nodes:
  - name: a
    class_name: p.Src
    hparams: {{}}
connections: []
"""

NODE = {
    "class_name": "Src",
    "full_path": "p.Src",
    "source": "plugin",
    "plugin_name": "p",
    "input_specs": [],
    "output_specs": [],
    "category": 0,
    "tags": [],
    "icon_svg": b"",
}


@pytest.fixture
def launch(qtbot, monkeypatch):
    """Run main() against a fake server; returns (window, register_plugins mock)."""
    previous_names = (QCoreApplication.applicationName(), QCoreApplication.organizationName())
    windows = []
    real_window = main_module.MainWindow

    def make_window(*args, **kwargs):
        window = real_window(*args, **kwargs)
        qtbot.addWidget(window)
        window.show = lambda: None
        windows.append(window)
        return window

    app = Mock()
    app.exec.return_value = 0
    monkeypatch.setattr(main_module, "QApplication", Mock(return_value=app))
    monkeypatch.setattr(main_module, "MainWindow", make_window)
    monkeypatch.setattr(
        main_module,
        "load_connection_settings",
        lambda: {"mode": "local", "host": "localhost", "port": 50051, "auto_start": False},
    )
    client = Mock(spec=CuvisAIClient)
    client.session_id = "s1"
    monkeypatch.setattr(main_module, "_connect", lambda host, port: client)
    register = Mock(return_value=PluginRegistration(nodes=[NODE], loaded=["p"]))
    monkeypatch.setattr(main_module, "register_plugins", register)
    collected = []
    monkeypatch.setattr(
        main_module, "collect_plugin_entries", lambda dirs: collected.append(list(dirs)) or []
    )
    monkeypatch.setattr(QMessageBox, "warning", Mock())

    def run(*args):
        result = CliRunner().invoke(main_module.main, [str(a) for a in args])
        assert result.exit_code == 0, result.output
        return windows[-1], register, collected

    yield run
    for window in windows:
        window._unsaved_changes = False
    QCoreApplication.setApplicationName(previous_names[0])
    QCoreApplication.setOrganizationName(previous_names[1])


def test_a_folder_registers_its_plugins_then_opens_its_first_pipeline(launch, tmp_path):
    for name in ("b", "a"):
        (tmp_path / f"{name}.yaml").write_text(PIPELINE.format(name=name), encoding="utf-8")
    (tmp_path / "plugins").mkdir()

    window, register, collected = launch(tmp_path)

    assert window.current_folder == tmp_path.absolute()
    assert window.current_file == (tmp_path / "a.yaml").absolute()
    assert register.call_count == 1
    assert register.call_args.kwargs == {"fresh_session": True}
    assert collected == [[tmp_path.absolute() / "plugins"]]
    assert window.node_registry.get_node_info("p.Src") is not None


def test_a_single_pipeline_registers_plugins_then_opens(launch, tmp_path):
    pipeline = tmp_path / "one.yaml"
    pipeline.write_text(PIPELINE.format(name="one"), encoding="utf-8")

    window, register, _ = launch(pipeline)

    assert window.current_folder is None
    assert window.current_file == pipeline
    assert register.call_count == 1
    assert register.call_args.kwargs == {"fresh_session": False}


@pytest.mark.parametrize(
    "args, listening, starts",
    [
        (["--start-server"], False, True),
        (["--start-server"], True, False),
        ([], False, False),
    ],
)
def test_start_server_starts_one_only_when_asked_and_nothing_listens(
    launch, monkeypatch, args, listening, starts
):
    monkeypatch.setattr(main_module, "is_listening", lambda host, port: listening)
    start = Mock()
    monkeypatch.setattr(main_module, "_start_local_server", start)

    launch(*args)

    assert start.called is starts
    if starts:
        assert start.call_args.args[1] == 50051


def test_a_failed_refresh_shows_no_stale_catalog(launch, tmp_path):
    """A refresh replaces the server session before it registers; when the
    registration fails, the nodes and plugin names of the old session must not
    stay on offer as if the server still had them."""
    pipeline = tmp_path / "one.yaml"
    pipeline.write_text(PIPELINE.format(name="one"), encoding="utf-8")
    window, register, _ = launch(pipeline)
    assert window.node_registry.get_all_nodes()

    register.side_effect = RuntimeError("server went away")
    window.refresh_nodes_action.trigger()

    assert window.node_registry.get_all_nodes() == []
    assert window._serializer.known_plugins == set()
    assert QMessageBox.warning.called
