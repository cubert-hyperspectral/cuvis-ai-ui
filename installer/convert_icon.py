"""Convert logo.png to logo.ico with multiple sizes for Windows."""

from pathlib import Path

from PIL import Image

SIZES = [16, 32, 48, 64, 128, 256]


def main() -> None:
    src = (
        Path(__file__).resolve().parent.parent / "cuvis_ai_ui" / "resources" / "icons" / "logo.png"
    )
    dst = Path(__file__).resolve().parent / "logo.ico"

    if not src.exists():
        raise FileNotFoundError(f"Source icon not found: {src}")

    img = Image.open(src)
    # RGBA for transparency support
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    icons = [img.resize((s, s), Image.Resampling.LANCZOS) for s in SIZES]
    icons[0].save(dst, format="ICO", sizes=[(s, s) for s in SIZES], append_images=icons[1:])
    print(f"Created {dst} ({dst.stat().st_size:,} bytes) with sizes {SIZES}")


if __name__ == "__main__":
    main()
