"""Pipeline folders in the main window: browsing, plugin hook-up, unsaved changes."""

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QMessageBox

from cuvis_ai_ui.main_window import MainWindow

PIPELINE = """metadata:
  name: {name}
plugins: [p]
nodes:
  - name: a
    class_name: p.Src
    hparams: {{}}
connections: []
"""


@pytest.fixture
def folder(tmp_path):
    for name in ("one", "two", "three"):
        (tmp_path / f"{name}.yaml").write_text(PIPELINE.format(name=name), encoding="utf-8")
    return tmp_path


@pytest.fixture
def answer(monkeypatch):
    """Stub the unsaved-changes question; returns the list of questions asked."""
    asked = []

    def set_answer(button):
        def question(*args, **kwargs):
            asked.append(args[2])
            return button

        monkeypatch.setattr(QMessageBox, "question", question)
        return asked

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    return set_answer


@pytest.fixture
def window(qtbot, answer):
    answer(QMessageBox.StandardButton.Cancel)
    win = MainWindow()
    qtbot.addWidget(win)
    yield win
    win._unsaved_changes = False


def _edit(window):
    node = window.graph.all_nodes()[0]
    node.set_pos(500, 500)


def test_open_folder_lists_it_and_opens_the_first_pipeline(window, folder):
    assert window.open_folder(folder)
    assert window.current_folder == folder
    assert window.current_file == folder / "one.yaml"
    assert window.pipeline_browser.pipelines == [
        folder / "one.yaml",
        folder / "three.yaml",
        folder / "two.yaml",
    ]
    assert window.pipeline_browser.list_widget.currentRow() == 0
    assert not window._pipelines_dock.isHidden()


def test_folder_changed_fires_before_the_pipeline_loads(window, folder):
    seen = []
    window.folder_changed.connect(lambda f: seen.append((f, window.current_file)))
    window.open_folder(folder, pipeline=folder / "two.yaml")
    assert seen == [(folder, None)]
    assert window.current_file == folder / "two.yaml"


def test_a_graph_edit_marks_the_pipeline_unsaved(window, folder):
    window.open_folder(folder)
    assert not window.windowTitle().startswith("*")
    _edit(window)
    assert window.windowTitle().startswith("*")


def test_browser_selection_keeps_edits_on_cancel(window, folder, answer):
    window.open_folder(folder)
    _edit(window)
    asked = answer(QMessageBox.StandardButton.Cancel)

    window.pipeline_browser.list_widget.setCurrentRow(2)

    assert len(asked) == 1
    assert window.current_file == folder / "one.yaml"
    assert window.pipeline_browser.list_widget.currentRow() == 0


def test_browser_selection_opens_after_discard(window, folder, answer):
    window.open_folder(folder)
    _edit(window)
    answer(QMessageBox.StandardButton.Discard)

    window.pipeline_browser.list_widget.setCurrentRow(2)

    assert window.current_file == folder / "two.yaml"
    assert not window.windowTitle().startswith("*")


def test_open_folder_asks_once_before_replacing_edits(window, folder, tmp_path_factory, answer):
    window.open_folder(folder)
    _edit(window)
    asked = answer(QMessageBox.StandardButton.Discard)
    other = tmp_path_factory.mktemp("other")
    (other / "x.yaml").write_text(PIPELINE.format(name="x"), encoding="utf-8")

    assert window.open_folder(other)

    assert len(asked) == 1
    assert window.current_file == other / "x.yaml"


def test_open_folder_cancel_keeps_the_old_folder(window, folder, tmp_path_factory, answer):
    window.open_folder(folder)
    _edit(window)
    answer(QMessageBox.StandardButton.Cancel)
    other = tmp_path_factory.mktemp("other")
    (other / "x.yaml").write_text(PIPELINE.format(name="x"), encoding="utf-8")

    assert not window.open_folder(other)
    assert window.current_folder == folder
    assert window.pipeline_browser.folder == folder


def test_an_empty_folder_leaves_the_graph_alone(window, folder, tmp_path_factory, answer):
    window.open_folder(folder)
    _edit(window)
    asked = answer(QMessageBox.StandardButton.Cancel)

    assert window.open_folder(tmp_path_factory.mktemp("empty"))

    assert asked == []
    assert window.current_file == folder / "one.yaml"


def test_unknown_plugins_warn_once_known_plugins_are_set(window, folder):
    window.set_known_plugins({"other"})
    window.open_folder(folder)
    assert any("Plugins not available: p" in w for w in window._serializer.last_load_warnings)


def test_cancelled_close_keeps_the_connection(window, folder, answer):
    client = Mock()
    window._client = client
    window.open_folder(folder)
    _edit(window)
    answer(QMessageBox.StandardButton.Cancel)

    assert not window.close()
    client.close.assert_not_called()
    window._client = None
