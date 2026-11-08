"""Write the cuvis-ai-core version into the source the installer ships.

``build.bat`` copies the core source without ``.git``, so setuptools-scm finds
no version in it. That source is installed editable into the per-user
server-venv, and cuvis-ai-core builds every per-pipeline environment from it
again as an editable path. A ``fallback_version`` in its
``[tool.setuptools_scm]`` table gives each of those builds the version.

Usage (from ``build.bat``)::

    uv run python installer/stamp_core_version.py <payload dir> <version>
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import click

TABLE = "[tool.setuptools_scm]"
_FALLBACK = re.compile(r"\s*fallback_version\s*=")


def stamp(pyproject: Path, version: str) -> None:
    """Set ``fallback_version`` in ``pyproject``'s setuptools-scm table.

    An existing ``fallback_version`` is replaced, the file's line endings are
    kept, and the result is parsed before it is written. Raises ValueError,
    leaving the file untouched, when the table is missing or the version does
    not make valid TOML.
    """
    text = pyproject.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)

    start = next((i for i, line in enumerate(lines) if line.strip() == TABLE), None)
    if start is None:
        raise ValueError(f"{pyproject} has no {TABLE} table")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")),
        len(lines),
    )

    entry = f'fallback_version = "{version}"{newline}'
    existing = next((i for i in range(start + 1, end) if _FALLBACK.match(lines[i])), None)
    if existing is None:
        lines.insert(start + 1, entry)
    else:
        lines[existing] = entry
    stamped = "".join(lines)

    try:
        written = tomllib.loads(stamped)["tool"]["setuptools_scm"].get("fallback_version")
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"version {version!r} does not make valid TOML: {exc}") from exc
    if written != version:
        raise ValueError(f"version {version!r} reads back as {written!r}")
    pyproject.write_bytes(stamped.encode("utf-8"))


@click.command()
@click.argument("payload_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("version")
def main(payload_dir: Path, version: str) -> None:
    """Stamp VERSION as fallback_version into PAYLOAD_DIR/pyproject.toml."""
    pyproject = payload_dir / "pyproject.toml"
    try:
        stamp(pyproject, version)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Stamped fallback_version = {version} into {pyproject}")


if __name__ == "__main__":
    main()
