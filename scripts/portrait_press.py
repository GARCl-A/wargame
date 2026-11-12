"""Print every portrait on the same paper with the same ink.

    python scripts/portrait_press.py                      # every portrait of the game, in place
    python scripts/portrait_press.py path/a.png path/b.png
    python scripts/portrait_press.py --out scratch/pressed # write copies, leave the originals

Generated portraits come out on papers from pale cream to dark yellow, with inks from grey to
black and now and then in colour. The press levels each one (its own darkest ink to INK, its own
paper to PAPER) and adds the same grain, so the pool reads as one book. Line weight is not
changed. A pressed file is marked in its PNG text and skipped on the next run, so pressing twice
is safe; run it after installing a new portrait. Needs Pillow and numpy.
"""

import argparse
import zlib
from pathlib import Path

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

ROOT = Path(__file__).resolve().parent.parent / "gartok" / "assets" / "portraits"
INK = np.array([38, 26, 14], dtype=np.float32)
PAPER = np.array([236, 221, 184], dtype=np.float32)
INK_PERCENTILE = 2
PAPER_PERCENTILE = 82
GRAIN = 3.5
MARK = "gartok_press"


def press(img, seed):
    rgba = np.asarray(img.convert("RGBA"), dtype=np.float32)
    lum = rgba[..., 0] * 0.299 + rgba[..., 1] * 0.587 + rgba[..., 2] * 0.114
    solid = lum[rgba[..., 3] > 200]
    lo, hi = np.percentile(solid, [INK_PERCENTILE, PAPER_PERCENTILE])
    t = np.clip((lum - lo) / max(hi - lo, 1.0), 0.0, 1.0)
    t = t * t * (3 - 2 * t)
    grain = np.random.default_rng(seed).uniform(-GRAIN, GRAIN, lum.shape).astype(np.float32)
    rgb = INK + (PAPER - INK) * t[..., None] + grain[..., None]
    out = np.dstack([np.clip(rgb, 0, 255), rgba[..., 3]]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", type=Path, help="portraits to press (default: all of them)")
    ap.add_argument("--out", type=Path, help="write the pressed copies here instead of in place")
    args = ap.parse_args()
    paths = args.paths or sorted(ROOT.rglob("*.png"))
    done = skipped = 0
    for path in paths:
        with Image.open(path) as img:
            img.load()
        if img.info.get(MARK):
            skipped += 1
            continue
        resolved = path.resolve()
        name = resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else path.name
        dest = args.out / name if args.out else path
        dest.parent.mkdir(parents=True, exist_ok=True)
        info = PngInfo()
        info.add_text(MARK, "1")
        press(img, zlib.crc32(name.encode())).save(dest, pnginfo=info, optimize=True)
        done += 1
    print(f"pressed {done}, already pressed {skipped}")


if __name__ == "__main__":
    main()
