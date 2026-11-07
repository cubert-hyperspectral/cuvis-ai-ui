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


def test_mirror_copies_released_manifests_and_drops_the_rest(tmp_path, monkeypatch):
    """Only git-pinned manifests are bundled, byte for byte; a manifest with a
    local path source is reported as skipped, and a catalog file that is gone
    upstream is deleted."""
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "old.yaml").write_text("name: old\n", encoding="utf-8")
    capabilities = b"capabilities:\n  - class_name: pkg.node.Node\n"
    blobs = {
        "keep.yaml": b"name: keep\nrepo: https://example.com/keep.git\ntag: v1\n" + capabilities,
        "local.yaml": b"name: local\npath: ../local\n" + capabilities,
    }
    monkeypatch.setattr(regenerate_catalog, "list_manifests", lambda repo, tag, d: sorted(blobs))
    monkeypatch.setattr(
        regenerate_catalog, "_git", lambda repo, *args: blobs[args[-1].rsplit("/", 1)[-1]]
    )

    names, skipped = regenerate_catalog.mirror(tmp_path, "v1", "plugins", catalog)

    assert names == ["keep.yaml"]
    assert skipped == ["local.yaml"]
    assert (catalog / "keep.yaml").read_bytes() == blobs["keep.yaml"]
    assert not (catalog / "local.yaml").exists()
    assert not (catalog / "old.yaml").exists()
    readme = (catalog / "README.md").read_text(encoding="utf-8")
    assert "1 released plugin manifest mirrored from cuvis-ai `v1`" in readme


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
