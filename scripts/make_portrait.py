#!/usr/bin/env python3
"""Turn a photo into the tone grid behind the halftone portrait (scripts/portrait.txt).

    pip install pillow
    python scripts/make_portrait.py photo.png

Each line of portrait.txt is one row of cells: "." is background (transparent in
the source photo) and 0-f is how dark the cell is. build_assets.py draws one dot
per cell from this file, so the build itself needs no imaging library.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

GRID = 64
OUT = Path(__file__).resolve().parent / "portrait.txt"
CROP = (0.14, 0.04, 0.86, 0.76)  # left, top, right, bottom, as fractions: head and shoulders


def main(src: str) -> None:
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    im = im.crop((round(CROP[0] * w), round(CROP[1] * h), round(CROP[2] * w), round(CROP[3] * h)))
    alpha = im.getchannel("A")
    subject = alpha.point(lambda a: 255 if a > 128 else 0)
    gray = ImageOps.autocontrast(im.convert("L"), cutoff=1, mask=subject)
    # Sharpen before sampling so eyes and mouth survive the drop to a coarse grid.
    gray = gray.filter(ImageFilter.UnsharpMask(radius=3, percent=180, threshold=2))
    cells = gray.resize((GRID, GRID), Image.Resampling.BOX)
    cover = alpha.resize((GRID, GRID), Image.Resampling.BOX)
    rows = []
    for y in range(GRID):
        row = ""
        for x in range(GRID):
            if cover.getpixel((x, y)) < 128:
                row += "."
            else:
                row += format(min(15, round((1 - cells.getpixel((x, y)) / 255) * 15)), "x")
        rows.append(row)
    OUT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"{OUT.name}: {GRID}x{GRID} cells from {Path(src).name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: make_portrait.py PHOTO")
    main(sys.argv[1])
