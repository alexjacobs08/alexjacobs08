#!/usr/bin/env python3
"""
Bake each project into a self-contained card: icon, name, two-line caption.

    python3 tools/make_cards.py        # -> assets/cards/<project>.png

Why cards and not the old table: a README cannot carry CSS or media queries, and on a
phone GitHub gives it ~308px. A four-column table needs ~420, so it scrolled sideways
with a column cut off. Inline images DO reflow — four across on desktop, two across on
a phone — but a caption cannot stay attached to an image that wraps, so the caption
has to live inside the image.

Cards are drawn at 3x (432px) and shown at 144px, with PIL's bitmap font scaled by
whole numbers so the lettering matches the pixel art. The first pass was 2x with the
caption at 2x scale — about 6px tall on a non-retina desktop, which is a squint. At
3x the caption lands near 15px line height; the price is captions of <= 17 characters.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICONS, OUT = ROOT / "assets" / "icons", ROOT / "assets" / "cards"
CARD_W, PAD, ICON = 432, 24, 384
TEXT_PAD = 6                  # text may run closer to the edge than the icon does
NAME_SCALE, CAP_SCALE = 5, 4
NAME_COL, CAP_COL = (254, 210, 130), (196, 212, 232)

CARDS = [   # icon file stem, display name, caption lines (<= 17 chars each)
    ("tinybench", "tinybench", ["8 LLMs, 40 tasks", "83% -> 99% tools"]),
    ("beatingBERT", "beatingBERT", ["encoders vs", "small LLMs"]),
    ("datasetFactory", "datasetFactory", ["synthetic RAG", "eval datasets"]),
    ("design-picker", "design-picker", ["pick a design", "language"]),
    ("artlens", "artlens", ["reverse search", "for fine art"]),
    ("poople-bench", "poople-bench", ["a daily LLM", "benchmark"]),
    ("s3verless", "s3verless", ["your database is", "a bucket now"]),
    ("fastApi-Integration-tests", "fastApi-tests", ["FastAPI testing,", "mocked properly"]),
]

FONT = ImageFont.load_default_imagefont() if hasattr(ImageFont, "load_default_imagefont") \
    else ImageFont.load_default()


def text_img(s, scale, colour):
    """Bitmap text, scaled by a whole number so it stays pixel-crisp."""
    l, t, r, b = FONT.getbbox(s)
    m = Image.new("L", (r, b), 0)
    ImageDraw.Draw(m).text((0, 0), s, fill=255, font=FONT)
    # crop sideways only: every line keeps the font's full height, so descenders do
    # not make one card a few pixels taller than its neighbour
    bx0, _, bx1, _ = m.getbbox()
    m = m.crop((bx0, 0, bx1, b)).resize(((bx1 - bx0) * scale, b * scale), Image.NEAREST)
    out = Image.new("RGBA", m.size, colour + (0,))
    out.putalpha(m.point(lambda v: 255 if v > 127 else 0))
    return out


def main():
    OUT.mkdir(exist_ok=True)
    total = 0
    for stem, name, cap in CARDS:
        icon = Image.open(ICONS / f"{stem}.png").convert("RGB")
        bg = icon.getpixel((3, 3))
        icon = icon.resize((ICON, ICON), Image.NEAREST)
        name_im = text_img(name, NAME_SCALE, NAME_COL)
        cap_ims = [text_img(c, CAP_SCALE, CAP_COL) for c in cap]
        assert name_im.width <= CARD_W - 2 * TEXT_PAD, (name, name_im.width)
        assert all(c.width <= CARD_W - 2 * TEXT_PAD for c in cap_ims), (name, [c.width for c in cap_ims])

        h = PAD + icon.height + 16 + name_im.height + 14 + sum(c.height + 6 for c in cap_ims) + PAD - 6
        card = Image.new("RGB", (CARD_W, h), bg)
        card.paste(icon, ((CARD_W - icon.width) // 2, PAD))
        y = PAD + icon.height + 16
        card.paste(name_im, ((CARD_W - name_im.width) // 2, y), name_im)
        y += name_im.height + 14
        for c in cap_ims:
            card.paste(c, ((CARD_W - c.width) // 2, y), c)
            y += c.height + 6
        p = OUT / f"{stem}.png"
        card.convert("P", palette=Image.ADAPTIVE, colors=48).save(p, optimize=True)
        total += p.stat().st_size
        print(f"  {p.name:34s} {card.size[0]}x{card.size[1]}")
    print(f"{len(CARDS)} cards, {total // 1024} KB")


if __name__ == "__main__":
    main()
