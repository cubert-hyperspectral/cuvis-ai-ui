"""The installer writes the cuvis-ai-core version into the source it ships."""

import tomllib

import pytest
from click.testing import CliRunner

CORE_PYPROJECT = """[build-system]
requires = ["setuptools>=64", "setuptools-scm>=8"]

[project]
name = "cuvis-ai-core"
dynamic = ["version"]

[tool.setuptools_scm]
version_scheme = "post-release"
local_scheme = "node-and-date"

[[tool.uv.index]]
name = "pytorch-cu128"
"""


def _scm(path):
    return tomllib.loads(path.read_text(encoding="utf-8"))["tool"]["setuptools_scm"]


def test_adds_the_fallback_version_and_keeps_the_rest(stamp_module, tmp_path):
    """setuptools-scm reads fallback_version when the source has no .git, which
    is how the installed server's source and every environment built from it
    get a version."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(CORE_PYPROJECT, encoding="utf-8")

    stamp_module.stamp(pyproject, "0.20.2")

    scm = _scm(pyproject)
    assert scm == {
        "version_scheme": "post-release",
        "local_scheme": "node-and-date",
        "fallback_version": "0.20.2",
    }
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert data["tool"]["uv"]["index"] == [{"name": "pytorch-cu128"}]


def test_replaces_an_existing_fallback_version(stamp_module, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        CORE_PYPROJECT.replace(
            'local_scheme = "node-and-date"\n',
            'local_scheme = "node-and-date"\nfallback_version = "0.0.0"\n',
        ),
        encoding="utf-8",
    )

    stamp_module.stamp(pyproject, "0.20.2")

    text = pyproject.read_text(encoding="utf-8")
    assert text.count("fallback_version") == 1
    assert _scm(pyproject)["fallback_version"] == "0.20.2"


def test_keeps_windows_line_endings(stamp_module, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(CORE_PYPROJECT.replace("\n", "\r\n").encode("utf-8"))

    stamp_module.stamp(pyproject, "0.20.2")

    raw = pyproject.read_bytes()
    assert b'fallback_version = "0.20.2"\r\n' in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")


def test_a_source_without_the_table_fails_and_stays_untouched(stamp_module, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    original = CORE_PYPROJECT.replace("[tool.setuptools_scm]\n", "[tool.other]\n")
    pyproject.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError, match="setuptools_scm"):
        stamp_module.stamp(pyproject, "0.20.2")
    assert pyproject.read_text(encoding="utf-8") == original


def test_a_version_that_breaks_the_toml_fails_and_stays_untouched(stamp_module, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(CORE_PYPROJECT, encoding="utf-8")

    with pytest.raises(ValueError):
        stamp_module.stamp(pyproject, 'bad"version')
    assert pyproject.read_text(encoding="utf-8") == CORE_PYPROJECT


def test_the_command_stamps_the_payload_pyproject(stamp_module, tmp_path):
    (tmp_path / "pyproject.toml").write_text(CORE_PYPROJECT, encoding="utf-8")

    result = CliRunner().invoke(stamp_module.main, [str(tmp_path), "0.20.2"])

    assert result.exit_code == 0, result.output
    assert _scm(tmp_path / "pyproject.toml")["fallback_version"] == "0.20.2"


def test_the_command_exits_non_zero_so_the_build_stops(stamp_module, tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")

    result = CliRunner().invoke(stamp_module.main, [str(tmp_path), "0.20.2"])

    assert result.exit_code != 0
    assert "setuptools_scm" in result.output


def test_a_payload_without_pyproject_exits_non_zero(stamp_module, tmp_path):
    result = CliRunner().invoke(stamp_module.main, [str(tmp_path), "0.20.2"])

    assert result.exit_code != 0
    assert "pyproject.toml" in result.output
    assert not (tmp_path / "pyproject.toml").exists()
