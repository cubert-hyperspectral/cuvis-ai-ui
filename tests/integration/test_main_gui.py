"""cuvis-ui wiring in main(): what the command line opens and how plugin refreshes land."""

import threading
from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from loguru import logger
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QMessageBox

from cuvis_ai_ui import main as main_module
from cuvis_ai_ui.grpc.client import CuvisAIClient, OperationCancelled
from cuvis_ai_ui.widgets.blocking_task import SERVER_WAIT_CANCELLED
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


# main() wires closures into each window it builds (refresh_plugins, the
# palette), so the window sits in reference cycles. qtbot.addWidget would
# deleteLater it; once a later test processes events, the C++ window goes
# while those cycles live, and the final garbage collection corrupts the heap.
# The windows are never shown, so they stay alive until the session ends.
_LAUNCHED_WINDOWS = []


@pytest.fixture
def launch(qapp, monkeypatch):
    """Run main() against a fake server; returns (window, register_plugins mock)."""
    previous_names = (QCoreApplication.applicationName(), QCoreApplication.organizationName())
    windows = []
    real_window = main_module.MainWindow

    def make_window(*args, **kwargs):
        window = real_window(*args, **kwargs)
        _LAUNCHED_WINDOWS.append(window)
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
    assert register.call_args.kwargs["fresh_session"] is True
    assert isinstance(register.call_args.kwargs["stop"], threading.Event)
    assert collected == [[tmp_path.absolute() / "plugins"]]
    assert window.node_registry.get_node_info("p.Src") is not None


def test_a_single_pipeline_registers_plugins_then_opens(launch, tmp_path):
    pipeline = tmp_path / "one.yaml"
    pipeline.write_text(PIPELINE.format(name="one"), encoding="utf-8")

    window, register, _ = launch(pipeline)

    assert window.current_folder is None
    assert window.current_file == pipeline
    assert register.call_count == 1
    assert register.call_args.kwargs["fresh_session"] is False


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
    start = Mock(return_value=(Mock(), False))
    monkeypatch.setattr(main_module, "_start_local_server", start)

    launch(*args)

    assert start.called is starts
    if starts:
        assert start.call_args.args == (50051,)


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
    assert "server went away" in QMessageBox.warning.call_args.args[2]


def test_unreadable_plugin_manifests_empty_the_catalog_and_log_the_traceback(
    launch, monkeypatch, tmp_path
):
    """A manifest that cannot be read fails the refresh before anything is
    registered: no stale catalog, a warning naming the error, and the log
    keeps the traceback."""
    pipeline = tmp_path / "one.yaml"
    pipeline.write_text(PIPELINE.format(name="one"), encoding="utf-8")
    window, register, _ = launch(pipeline)
    QMessageBox.warning.reset_mock()

    def unreadable(dirs):
        raise ValueError("bad manifest: p.yaml")

    monkeypatch.setattr(main_module, "collect_plugin_entries", unreadable)
    records = []
    sink = logger.add(lambda message: records.append(message.record), level="ERROR")
    try:
        window.refresh_nodes_action.trigger()
    finally:
        logger.remove(sink)

    assert register.call_count == 1
    assert window.node_registry.get_all_nodes() == []
    assert window._serializer.known_plugins == set()
    assert "bad manifest: p.yaml" in QMessageBox.warning.call_args.args[2]
    assert [r["exception"].type for r in records if r["exception"]] == [ValueError]


def test_a_cancelled_refresh_empties_the_catalog_without_an_error_box(launch, qtbot, tmp_path):
    """Cancel during registration may leave part of the plugin set in a fresh
    session, so the palette empties as after a failure, but the user cancelled:
    a status note, no error box."""
    pipeline = tmp_path / "one.yaml"
    pipeline.write_text(PIPELINE.format(name="one"), encoding="utf-8")
    window, register, _ = launch(pipeline)
    QMessageBox.warning.reset_mock()

    register.side_effect = OperationCancelled()
    window.refresh_nodes_action.trigger()

    assert window.node_registry.get_all_nodes() == []
    assert window._serializer.known_plugins == set()
    assert not QMessageBox.warning.called
    qtbot.waitUntil(
        lambda: window.statusBar().currentMessage().startswith("Plugin registration cancelled"),
        timeout=1000,
    )


def test_a_cancelled_registration_note_outlasts_the_opened_message(
    launch, monkeypatch, qtbot, tmp_path
):
    """Opening a folder registers its plugins, then opens its first pipeline,
    whose "Opened:" message must not wipe the note on why the palette is empty."""
    (tmp_path / "a.yaml").write_text(PIPELINE.format(name="a"), encoding="utf-8")
    monkeypatch.setattr(main_module, "register_plugins", Mock(side_effect=OperationCancelled()))

    window, _, _ = launch(tmp_path)

    assert window.current_file == (tmp_path / "a.yaml").absolute()
    assert window.node_registry.get_all_nodes() == []
    qtbot.waitUntil(
        lambda: window.statusBar().currentMessage().startswith("Plugin registration cancelled"),
        timeout=1000,
    )


def test_a_cancelled_server_wait_skips_connecting(launch, monkeypatch, tmp_path):
    """After the user stops waiting for the server, no connect attempt and no
    "Server Not Running" box follow; the status bar says the server keeps
    starting."""
    pipeline = tmp_path / "one.yaml"
    pipeline.write_text(PIPELINE.format(name="one"), encoding="utf-8")
    monkeypatch.setattr(main_module, "is_listening", lambda host, port: False)
    manager = Mock()
    monkeypatch.setattr(main_module, "_start_local_server", Mock(return_value=(manager, True)))
    connect = Mock()
    monkeypatch.setattr(main_module, "_connect", connect)

    window, register, _ = launch(pipeline, "--start-server")

    connect.assert_not_called()
    register.assert_not_called()
    assert window.client is None
    assert window.server_manager is manager
    assert window.statusBar().currentMessage() == SERVER_WAIT_CANCELLED
    # Only the pipeline's own load warning (no server, so no nodes) may show
    titles = {c.args[1] for c in QMessageBox.warning.call_args_list}
    assert titles <= {"Pipeline Load Warnings"}


@pytest.fixture
def connect_env(qapp, monkeypatch):
    monkeypatch.setattr(main_module, "is_listening", lambda host, port: True)
    client = Mock(spec=CuvisAIClient)
    client.session_id = "s1"
    monkeypatch.setattr(main_module, "CuvisAIClient", Mock(return_value=client))
    monkeypatch.setattr(QMessageBox, "warning", Mock())
    return client


def test_connect_hands_the_stop_event_to_the_client(connect_env):
    assert main_module._connect("localhost", 50200) is connect_env
    assert isinstance(connect_env.connect.call_args.kwargs["stop"], threading.Event)


def test_a_cancelled_connect_returns_no_client_and_no_box(connect_env):
    connect_env.connect.side_effect = OperationCancelled()
    assert main_module._connect("localhost", 50200) is None
    assert not QMessageBox.warning.called


def test_a_failed_connect_names_the_error(connect_env):
    connect_env.connect.side_effect = ConnectionError("handshake refused")
    assert main_module._connect("localhost", 50200) is None
    assert "handshake refused" in QMessageBox.warning.call_args.args[2]
