"""Generate platform icons from the user's square PNG, without changing artwork."""

import argparse
from pathlib import Path


def prepare_icons(root: Path) -> Path:
    from PIL import Image

    source = root / "assets/icon.png"
    with Image.open(source) as image:
        if image.width != image.height or image.width < 256:
            raise ValueError("assets/icon.png must be square and at least 256 × 256 pixels")
        image = image.convert("RGBA")
        output = root / "build/icons"
        output.mkdir(parents=True, exist_ok=True)
        image.resize((1024, 1024), Image.Resampling.LANCZOS).save(output / "icon.icns", format="ICNS")
        image.resize((256, 256), Image.Resampling.LANCZOS).save(
            output / "icon.ico", format="ICO", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
        image.resize((512, 512), Image.Resampling.LANCZOS).save(output / "icon.png")
    return output


def main():
    parser = argparse.ArgumentParser(description="Generate ICNS, ICO and PNG application icons")
    parser.parse_args()
    output = prepare_icons(Path(__file__).resolve().parents[1])
    print(f"Icons generated: {output}")


if __name__ == "__main__":
    main()
