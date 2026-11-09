"""Point the installer at a Cuvis SDK release on GitHub.

The installer offers the Cuvis SDK's Windows installer from a release of
cubert-hyperspectral/cuvis.sdk. ``installer/cuvis_sdk.iss`` names that asset,
its URL, its SHA-256 (from the release's ``SHA256SUMS.txt``) and its size, and
the Inno script includes it, so a release build needs no network for the SDK.

Run this when the pin moves (keep it in the ``cuvis-il`` range of the
cuvis-ai-dataloader tag the bundled catalog pins)::

    uv run python installer/update_cuvis_sdk.py 3.6.1
"""

from __future__ import annotations

import re
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import click

REPO = "cubert-hyperspectral/cuvis.sdk"
MANIFEST = Path(__file__).resolve().parent / "cuvis_sdk.iss"
_VERSION = re.compile(r"\d+\.\d+\.\d+")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SUMS_LINE = re.compile(r"(\S+)\s+\*?(?:\./)?(.+)")
_DEFINE = re.compile(r'#define\s+(\w+)\s+"([^"]*)"')
DEFINES = ("CuvisSdkVersion", "CuvisSdkAsset", "CuvisSdkUrl", "CuvisSdkSha256", "CuvisSdkSizeMB")


class SdkAsset(NamedTuple):
    """The SDK installer the Inno script downloads."""

    version: str
    name: str
    url: str
    sha256: str
    size_mb: int


def release_base(version: str) -> str:
    """Download prefix of release ``v<version>``."""
    return f"https://github.com/{REPO}/releases/download/v{version}/"


def _asset_pattern(version: str) -> re.Pattern[str]:
    return re.compile(rf"Cuvis_C_SDK_Installer_{re.escape(version)}_Windows_amd64_.+\.exe")


def pick_asset(sums: str, version: str) -> tuple[str, str]:
    """The Windows installer's name and SHA-256 from a ``SHA256SUMS.txt`` text."""
    pattern = _asset_pattern(version)
    found = []
    for line in sums.splitlines():
        match = _SUMS_LINE.fullmatch(line.strip())
        if match and pattern.fullmatch(match.group(2).strip()):
            found.append((match.group(2).strip(), match.group(1).lower()))
    if not found:
        raise ValueError(
            f"SHA256SUMS.txt of v{version} lists no "
            f"Cuvis_C_SDK_Installer_{version}_Windows_amd64_*.exe"
        )
    if len(found) > 1:
        names = ", ".join(name for name, _ in found)
        raise ValueError(
            f"SHA256SUMS.txt of v{version} lists {len(found)} Windows installers: {names}"
        )
    name, sha = found[0]
    if not _SHA256.fullmatch(sha):
        raise ValueError(f"SHA-256 of {name} is not 64 hex characters: {sha!r}")
    return name, sha


def resolve(
    version: str,
    fetch_text: Callable[[str], str],
    fetch_size: Callable[[str], int | None],
) -> SdkAsset:
    """Look up the Windows installer of release ``v<version>``."""
    if not _VERSION.fullmatch(version):
        raise ValueError(f"version must be X.Y.Z, got {version!r}")
    base = release_base(version)
    try:
        sums = fetch_text(base + "SHA256SUMS.txt")
    except OSError as exc:
        raise ValueError(f"release v{version} of {REPO} could not be read: {exc}") from exc
    name, sha = pick_asset(sums, version)
    url = base + name
    try:
        size = fetch_size(url)
    except OSError as exc:
        raise ValueError(f"size of {url} could not be read: {exc}") from exc
    if not size:
        raise ValueError(f"the server reported no size for {url}")
    return SdkAsset(version, name, url, sha, round(size / 1_000_000))


def render(asset: SdkAsset) -> str:
    """The text of ``cuvis_sdk.iss`` for ``asset``."""
    values = (asset.version, asset.name, asset.url, asset.sha256, str(asset.size_mb))
    defines = "".join(
        f'#define {name} "{value}"\n' for name, value in zip(DEFINES, values, strict=True)
    )
    return (
        "; Cuvis SDK release the installer offers, written by installer/update_cuvis_sdk.py.\n"
        "; Keep the version in the cuvis-il range of the cuvis-ai-dataloader tag that\n"
        "; cuvis_ai_ui/catalog/cuvis_ai_dataloader.yaml pins, and move it with:\n"
        ";   uv run python installer/update_cuvis_sdk.py <version>\n" + defines
    )


def parse_manifest(text: str) -> dict[str, str]:
    """The ``#define`` values of a ``cuvis_sdk.iss`` text."""
    return {m.group(1): m.group(2) for m in map(_DEFINE.fullmatch, text.splitlines()) if m}


def validate_manifest(text: str) -> SdkAsset:
    """Check a ``cuvis_sdk.iss`` text and return its asset; ValueError names the problem."""
    values = parse_manifest(text)
    missing = [name for name in DEFINES if name not in values]
    if missing:
        raise ValueError(f"cuvis_sdk.iss lacks {', '.join(missing)}")
    version, name, url, sha, size = (values[name] for name in DEFINES)
    if not _VERSION.fullmatch(version):
        raise ValueError(f"CuvisSdkVersion must be X.Y.Z, got {version!r}")
    if not _asset_pattern(version).fullmatch(name):
        raise ValueError(f"CuvisSdkAsset {name!r} is not the Windows installer of {version}")
    if url != release_base(version) + name:
        raise ValueError(f"CuvisSdkUrl {url!r} is not the release URL of {name}")
    if not _SHA256.fullmatch(sha):
        raise ValueError(f"CuvisSdkSha256 is not a SHA-256 (64 lowercase hex characters): {sha!r}")
    if not size.isdigit() or int(size) <= 0:
        raise ValueError(f"CuvisSdkSizeMB must be a positive size in MB, got {size!r}")
    return SdkAsset(version, name, url, sha, int(size))


def fetch_text(url: str) -> str:
    """GET ``url`` as text."""
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 (fixed https URL)
        return response.read().decode("utf-8")


def fetch_size(url: str) -> int | None:
    """Content length of ``url`` from a HEAD request; urllib keeps HEAD across redirects."""
    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 (fixed https URL)
        length = response.headers.get("Content-Length")
    return int(length) if length and length.isdigit() else None


@click.command()
@click.argument("version")
@click.option(
    "--manifest",
    type=click.Path(dir_okay=False, path_type=Path),
    default=MANIFEST,
    show_default=True,
    help="The Inno include to rewrite.",
)
def main(version: str, manifest: Path) -> None:
    """Point the installer at the Windows SDK installer of release vVERSION."""
    try:
        asset = resolve(version, fetch_text, fetch_size)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    manifest.write_text(render(asset), encoding="utf-8", newline="\n")
    click.echo(f"{asset.name} ({asset.size_mb} MB, sha256 {asset.sha256}) -> {manifest}")


if __name__ == "__main__":
    main()
