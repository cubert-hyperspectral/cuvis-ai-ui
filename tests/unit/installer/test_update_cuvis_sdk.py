"""The installer offers the Cuvis SDK release named in installer/cuvis_sdk.iss."""

import re

import pytest
from click.testing import CliRunner

from .conftest import INSTALLER_DIR

SHA = "7c6640d3b25870290763500edd3aa5a8f716f8034548d73e3fd20f4e0de78a82"
OTHER_SHA = "0" * 64
ASSET = "Cuvis_C_SDK_Installer_3.6.1_Windows_amd64_cuda12.9.exe"
URL = f"https://github.com/cubert-hyperspectral/cuvis.sdk/releases/download/v3.6.1/{ASSET}"

SUMS = f"""{OTHER_SHA}  cuviscommon_3.6.1-0_Ubuntu22.04_amd64_cuda12.9.deb
{SHA} *./{ASSET}
{OTHER_SHA}  RELEASE-NOTES_v3.6.1.pdf
"""


def _fetchers(sums=SUMS, size=206_615_384, fail=None):
    """Fake GET and HEAD: no network in tests."""
    calls = []

    def fetch_text(url):
        calls.append(("GET", url))
        if fail:
            raise OSError(fail)
        return sums

    def fetch_size(url):
        calls.append(("HEAD", url))
        return size

    return fetch_text, fetch_size, calls


@pytest.mark.parametrize(
    "line",
    [f"{SHA}  {ASSET}", f"{SHA} *{ASSET}", f"{SHA}  ./{ASSET}", f"{SHA.upper()}\t{ASSET}"],
    ids=["two-spaces", "binary-star", "dot-slash", "upper-tab"],
)
def test_picks_the_windows_installer_from_the_checksums(update_module, line):
    name, sha = update_module.pick_asset(f"{OTHER_SHA}  notes.pdf\n{line}\n", "3.6.1")
    assert (name, sha) == (ASSET, SHA)


def test_no_windows_installer_in_the_release_fails(update_module):
    with pytest.raises(ValueError, match="no Cuvis_C_SDK_Installer_3.6.1_Windows_amd64"):
        update_module.pick_asset(f"{OTHER_SHA}  notes.pdf\n", "3.6.1")


def test_two_windows_installers_fail(update_module):
    second = ASSET.replace("cuda12.9", "cuda13.0")
    with pytest.raises(ValueError, match="2 Windows installers"):
        update_module.pick_asset(f"{SHA}  {ASSET}\n{OTHER_SHA}  {second}\n", "3.6.1")


def test_an_installer_of_another_version_is_not_taken(update_module):
    other = ASSET.replace("3.6.1", "3.6.0")
    with pytest.raises(ValueError, match="no Cuvis_C_SDK_Installer_3.6.1"):
        update_module.pick_asset(f"{SHA}  {other}\n", "3.6.1")


def test_a_malformed_hash_fails(update_module):
    with pytest.raises(ValueError, match="SHA-256"):
        update_module.pick_asset(f"{SHA[:-1]}  {ASSET}\n", "3.6.1")


def test_resolve_reads_the_sums_and_the_size_of_the_release(update_module):
    fetch_text, fetch_size, calls = _fetchers()

    asset = update_module.resolve("3.6.1", fetch_text, fetch_size)

    assert asset == update_module.SdkAsset(
        version="3.6.1", name=ASSET, url=URL, sha256=SHA, size_mb=207
    )
    base = "https://github.com/cubert-hyperspectral/cuvis.sdk/releases/download/v3.6.1/"
    assert calls == [("GET", base + "SHA256SUMS.txt"), ("HEAD", URL)]


def test_a_missing_release_fails_with_the_release_named(update_module):
    fetch_text, fetch_size, _ = _fetchers(fail="HTTP Error 404: Not Found")
    with pytest.raises(ValueError, match=r"v9\.9\.9 of cubert-hyperspectral/cuvis\.sdk.*404"):
        update_module.resolve("9.9.9", fetch_text, fetch_size)


@pytest.mark.parametrize("size", [None, 0])
def test_an_unknown_size_fails(update_module, size):
    fetch_text, fetch_size, _ = _fetchers(size=size)
    with pytest.raises(ValueError, match="size"):
        update_module.resolve("3.6.1", fetch_text, fetch_size)


def test_a_version_that_is_not_x_y_z_fails_before_any_request(update_module):
    fetch_text, fetch_size, calls = _fetchers()
    with pytest.raises(ValueError, match="X.Y.Z"):
        update_module.resolve("v3.6", fetch_text, fetch_size)
    assert calls == []


def test_the_written_manifest_reads_back_as_the_asset(update_module):
    asset = update_module.SdkAsset("3.6.1", ASSET, URL, SHA, 207)

    text = update_module.render(asset)

    assert update_module.parse_manifest(text) == {
        "CuvisSdkVersion": "3.6.1",
        "CuvisSdkAsset": ASSET,
        "CuvisSdkUrl": URL,
        "CuvisSdkSha256": SHA,
        "CuvisSdkSizeMB": "207",
    }
    assert update_module.validate_manifest(text) == asset


def test_cli_rewrites_the_manifest(update_module, tmp_path, monkeypatch):
    fetch_text, fetch_size, _ = _fetchers()
    monkeypatch.setattr(update_module, "fetch_text", fetch_text)
    monkeypatch.setattr(update_module, "fetch_size", fetch_size)
    manifest = tmp_path / "cuvis_sdk.iss"

    result = CliRunner().invoke(update_module.main, ["3.6.1", "--manifest", str(manifest)])

    assert result.exit_code == 0, result.output
    assert ASSET in result.output
    assert update_module.validate_manifest(manifest.read_text(encoding="utf-8")).sha256 == SHA


def test_cli_leaves_the_manifest_alone_when_the_release_is_missing(
    update_module, tmp_path, monkeypatch
):
    fetch_text, fetch_size, _ = _fetchers(fail="HTTP Error 404: Not Found")
    monkeypatch.setattr(update_module, "fetch_text", fetch_text)
    monkeypatch.setattr(update_module, "fetch_size", fetch_size)
    manifest = tmp_path / "cuvis_sdk.iss"
    manifest.write_text("unchanged", encoding="utf-8")

    result = CliRunner().invoke(update_module.main, ["9.9.9", "--manifest", str(manifest)])

    assert result.exit_code == 1
    assert "v9.9.9" in result.output
    assert manifest.read_text(encoding="utf-8") == "unchanged"


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        ('"3.6.1"', '"3.6"', "X.Y.Z"),
        (f'"{SHA}"', f'"{SHA[:-2]}"', "SHA-256"),
        ("/v3.6.1/", "/v3.6.0/", "URL"),
        ('"207"', '"0"', "size"),
    ],
    ids=["version", "hash", "url", "size"],
)
def test_a_broken_hand_edit_fails_validation(update_module, old, new, problem):
    text = update_module.render(update_module.SdkAsset("3.6.1", ASSET, URL, SHA, 207))
    with pytest.raises(ValueError, match=problem):
        update_module.validate_manifest(text.replace(old, new, 1))


def test_a_missing_define_fails_validation(update_module):
    text = update_module.render(update_module.SdkAsset("3.6.1", ASSET, URL, SHA, 207))
    without = "\n".join(line for line in text.splitlines() if "CuvisSdkUrl" not in line)
    with pytest.raises(ValueError, match="CuvisSdkUrl"):
        update_module.validate_manifest(without)


def test_the_shipped_manifest_is_consistent(update_module):
    """The installer includes this file; a hand edit that breaks it fails here."""
    text = (INSTALLER_DIR / "cuvis_sdk.iss").read_text(encoding="utf-8")

    asset = update_module.validate_manifest(text)

    assert re.fullmatch(r"\d+\.\d+\.\d+", asset.version)
    assert '#include "cuvis_sdk.iss"' in (INSTALLER_DIR / "cuvis_ai_ui.iss").read_text(
        encoding="utf-8"
    )
