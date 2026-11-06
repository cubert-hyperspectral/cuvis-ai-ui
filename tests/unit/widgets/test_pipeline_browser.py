"""Tests for the pipelines browser dock widget."""

import pytest
from PySide6.QtCore import Qt

from cuvis_ai_ui.widgets.pipeline_browser import PipelineBrowser


@pytest.fixture
def folder(tmp_path):
    for name in ("b_second.yaml", "a_first.yaml", "notes.md"):
        (tmp_path / name).write_text("nodes: []\n", encoding="utf-8")
    (tmp_path / "plugins").mkdir()
    (tmp_path / "plugins" / "p.yaml").write_text("name: p\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def browser(qtbot):
    widget = PipelineBrowser()
    qtbot.addWidget(widget)
    return widget


def test_lists_the_folder_pipelines_in_order(browser, folder):
    browser.set_folder(folder)
    assert browser.folder == folder
    assert browser.pipelines == [folder / "a_first.yaml", folder / "b_second.yaml"]
    assert browser.list_widget.item(0).text() == "a_first"
    assert browser.list_widget.item(0).toolTip() == str(folder / "a_first.yaml")


def test_selecting_a_pipeline_emits_its_path(browser, folder, qtbot):
    browser.set_folder(folder)
    with qtbot.waitSignal(browser.pipeline_selected) as signal:
        browser.list_widget.setCurrentRow(1)
    assert signal.args == [str(folder / "b_second.yaml")]


def test_arrow_keys_move_through_pipelines(browser, folder, qtbot):
    browser.set_folder(folder)
    browser.select(folder / "a_first.yaml")
    with qtbot.waitSignal(browser.pipeline_selected) as signal:
        qtbot.keyClick(browser.list_widget, Qt.Key.Key_Down)
    assert signal.args == [str(folder / "b_second.yaml")]


def test_select_marks_a_pipeline_without_emitting(browser, folder, qtbot):
    browser.set_folder(folder)
    with qtbot.assertNotEmitted(browser.pipeline_selected):
        browser.select(folder / "b_second.yaml")
    assert browser.list_widget.currentRow() == 1


def test_select_of_another_file_clears_the_mark(browser, folder):
    browser.set_folder(folder)
    browser.select(folder / "a_first.yaml")
    browser.select(folder / "elsewhere.yaml")
    assert browser.list_widget.currentRow() == -1


def test_empty_folder_says_so(browser, tmp_path):
    browser.set_folder(tmp_path)
    assert browser.pipelines == []
    assert not browser.empty_label.isHidden()
    assert "No pipelines" in browser.empty_label.text()


def test_without_a_folder_points_to_open_folder(browser):
    browser.set_folder(None)
    assert browser.folder is None
    assert "Open Folder" in browser.empty_label.text()


def test_a_new_folder_replaces_the_list(browser, folder, tmp_path_factory):
    browser.set_folder(folder)
    other = tmp_path_factory.mktemp("other")
    (other / "only.yaml").write_text("nodes: []\n", encoding="utf-8")
    browser.set_folder(other)
    assert browser.pipelines == [other / "only.yaml"]
    assert browser.empty_label.isHidden()
