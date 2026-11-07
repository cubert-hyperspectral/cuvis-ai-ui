"""Tests for the regenerate_catalog script's git error handling."""

import subprocess
from pathlib import Path

from click.testing import CliRunner

import scripts.regenerate_catalog as regenerate_catalog
from scripts.regenerate_catalog import list_manifests, main


def test_list_manifests_keeps_names_with_spaces(monkeypatch):
    def fake_git(repo, *args):
        return b"a.yaml\0custom plugin.yaml\0README.md\0"

    monkeypatch.setattr(regenerate_catalog, "_git", fake_git)

    names = list_manifests(Path("."), "v9.9.9", "cuvis_ai/configs/plugins")

    assert names == ["a.yaml", "custom plugin.yaml"]


def test_git_failure_is_reported_as_a_click_error(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(128, args[0], stderr=b"fatal: Not a valid object name")

    monkeypatch.setattr(regenerate_catalog.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(main, ["--tag", "v9.9.9", "--cuvis-ai", str(Path("."))])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "fatal: Not a valid object name" in result.output
    assert result.exc_info[0] is not subprocess.CalledProcessError
