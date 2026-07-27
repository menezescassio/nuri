"""Turn the supplied logo into a transparent mark and the favicon set.

    uv run --with pillow python tools/build_mark.py <source.png>

The source is the mark on a white background with a lot of surrounding space.
This crops to the ink, removes the white, and writes the sizes the page needs.

Removing the white is done by un-matting rather than by keying out pixels above a
threshold. A threshold leaves a white fringe on every antialiased edge, which is
visible the moment the mark sits on a dark background, and this page has a dark
mode. Un-matting recovers, for each pixel, the colour and coverage that would
have produced it over white:

    alpha = 1 - min(r, g, b)              coverage, from the least saturated channel
    colour = (pixel - (1 - alpha)) / alpha  the colour before it was composited

which leaves the edges smooth against any backdrop.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
ASSETS = HERE / "assets"
SIZES = {"nuri-mark-512.png": 512, "nuri-mark-180.png": 180, "nuri-mark-64.png": 64,
         "nuri-mark-32.png": 32}

# The mark ships in two inks. The supplied artwork is the light-mode one. On the
# dark surface it sits darker than the wordmark beside it, so a lightened variant
# is generated from the same alpha channel and swapped by prefers-color-scheme.
DARK_INK = (171, 92, 245)


def unmatte(image: Image.Image) -> Image.Image:
    image = image.convert("RGB")
    out = Image.new("RGBA", image.size)
    src, dst = image.load(), out.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = src[x, y]
            alpha = 255 - min(r, g, b)
            # The source carries a faint off-white vignette in the corners, a few
            # levels below pure white. Anything that close to white is background;
            # real ink on this mark sits far darker, so this cannot eat an edge.
            if alpha <= 10:
                dst[x, y] = (0, 0, 0, 0)
                continue
            a = alpha / 255.0
            colour = tuple(
                max(0, min(255, round((channel / 255.0 - (1 - a)) / a * 255)))
                for channel in (r, g, b)
            )
            dst[x, y] = (*colour, alpha)
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    source = Path(argv[1])
    if not source.exists():
        print(f"{source}: not found", file=sys.stderr)
        return 1

    mark = unmatte(Image.open(source))
    box = mark.getbbox()
    if box is None:
        print("source appears to be blank", file=sys.stderr)
        return 1
    mark = mark.crop(box)

    # Square it with a little breathing room, so the favicon is not cropped tight
    # against the glyph and the mark centres cleanly beside the wordmark.
    side = round(max(mark.size) * 1.14)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(mark, ((side - mark.width) // 2, (side - mark.height) // 2), mark)

    ASSETS.mkdir(exist_ok=True)
    for name, size in SIZES.items():
        canvas.resize((size, size), Image.LANCZOS).save(ASSETS / name)
        print(f"  assets/{name}")

    # Recolour, keeping the coverage: only the ink changes, edges stay smooth.
    dark = Image.new("RGBA", canvas.size)
    src, dst = canvas.load(), dark.load()
    for y in range(canvas.height):
        for x in range(canvas.width):
            dst[x, y] = (*DARK_INK, src[x, y][3])
    for size in (512, 64, 32):
        dark.resize((size, size), Image.LANCZOS).save(ASSETS / f"nuri-mark-dark-{size}.png")
        print(f"  assets/nuri-mark-dark-{size}.png")
    canvas.resize((32, 32), Image.LANCZOS).save(ASSETS / "favicon.ico",
                                                sizes=[(16, 16), (32, 32)])
    print("  assets/favicon.ico")
    print(f"cropped from {Image.open(source).size} to {mark.size}, squared to {side}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
