#!/usr/bin/env python3
"""
Draw the taco assembly line procedurally and export it as a seamless looping GIF.

    python3 tools/make_banner.py                  # -> assets/banner.gif
    python3 tools/make_banner.py --still          # -> assets/banner.png (frame 0)

Why this is drawn rather than generated: the generated banner is a *render* of an
assembly line, not one laid out on a grid, so nothing in it can be moved. Measured
repeat correlation along its conveyor was 0.33 — no seamless scroll available. Drawing
it on a real pixel grid makes every element addressable and the loop exact.

HOW THE LOOP CLOSES (the one idea the whole file rests on)

    Every taco's appearance is a pure function of its x position, f(x): a flat disc
    before the press, an empty shell after it, filled after the hoppers, wrapped after
    the wrapper. Tacos are spaced exactly STATION_GAP apart, and over one loop every
    taco advances exactly STATION_GAP.

    So at the last frame taco k sits precisely where taco k+1 sat at frame 0 — and
    because appearance depends only on position, it *looks* like it too. The composite
    is pixel-identical to frame 0 without anything being faded or cross-dissolved.

Everything else is tied to the same phase so it inherits the loop: the belt tread
period divides STATION_GAP, and each machine animates off the distance to the nearest
taco, which is itself periodic in the phase.

Palette is sampled from the generated banner, so this matches the avatar and the
project icons.
"""
import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent

# ── geometry, in base pixels (the art is drawn small, then scaled by whole numbers) ──
W, H = 258, 64
SCALE = 8                      # 258x64 -> 2064x512; GitHub shows it near 830px,
                               # so a big whole-number source stays sharp when shrunk
STATIONS = [26, 78, 130, 182, 234]
STATION_GAP = 52               # also the taco spacing: this is what makes the loop work
FRAMES = 13                    # STATION_GAP / FRAMES = 4px of travel per frame
TREAD = 13                     # must divide STATION_GAP (52) so the belt loops, and must
                               # NOT divide the 4px per-frame step or the tread would sit
                               # still while the tacos move. 13 satisfies both.

BELT_Y = 42                    # top surface of the belt
FLOOR_Y = 52

# ── palette, sampled from style-refs/out/ban2-b-1.png ──
BG        = (29, 70, 128)
BG_DARK   = (41, 38, 91)
INK       = (1, 1, 1)
STEEL_HI  = (211, 211, 211)
STEEL     = (187, 186, 187)
STEEL_MID = (140, 140, 140)
STEEL_LO  = (99, 99, 99)
STEEL_DK  = (67, 67, 67)
PAPER     = (243, 243, 243)
SHELL     = (253, 149, 43)
SHELL_HI  = (254, 202, 122)
SHELL_LO  = (189, 91, 36)
DOUGH     = (229, 189, 125)
TOMATO    = (195, 58, 27)
EMBER     = (244, 99, 26)
LETTUCE   = (78, 158, 62)
KHAKI     = (217, 208, 133)
SKIN      = (232, 176, 122)
CRATE     = (138, 90, 43)
CRATE_HI  = (170, 118, 62)


class Canvas:
    """Thin wrapper so every draw call speaks in base pixels."""

    def __init__(self):
        self.im = Image.new("RGB", (W, H), BG)
        self.d = ImageDraw.Draw(self.im)

    def rect(self, x0, y0, x1, y1, c):
        self.d.rectangle([x0, y0, x1, y1], fill=c)

    def box(self, x0, y0, x1, y1, fill, outline=INK):
        self.d.rectangle([x0, y0, x1, y1], fill=fill, outline=outline)

    def shell(self, cx, bottom, w, depth, fill, outline=INK):
        """Upward-opening half ellipse — the taco shell. Wider than deep, or it
        reads as a bucket rather than a taco."""
        self.d.pieslice([cx - w // 2, bottom - 2 * depth, cx + w // 2, bottom],
                        0, 180, fill=fill, outline=outline)


# ── the item: appearance is a pure function of x ───────────────────────────
def draw_taco(c: Canvas, x: int):
    """Whatever is on the belt at this x. Appearance depends on x and nothing else."""
    if x < 8 or x > STATIONS[4] - 6:
        return                                   # still in the crate, or packed away
    # PIL's pieslice fill stops ~2px short of the bbox edge, so a shell anchored at
    # BELT_Y - 1 hovers above the belt. Anchor lower and it sits on it.
    b = BELT_Y + 2

    if x < STATIONS[1]:                          # flat tortilla disc
        c.d.ellipse([x - 6, b - 3, x + 6, b], fill=DOUGH, outline=INK)
        c.rect(x - 3, b - 2, x + 2, b - 2, (245, 216, 164))
        return

    top = b - 6                                  # shell now sits on the belt, not in it
    c.shell(x, b, 15, 6, SHELL)                  # folded shell from here on
    c.rect(x - 5, top + 1, x - 2, top + 1, SHELL_HI)   # highlight along the rim
    c.rect(x - 4, b - 1, x + 4, b - 1, SHELL_LO)       # shaded underside
    c.rect(x - 4, top, x + 4, top, SHELL_LO)           # the opening, between the tips
    for tx in (x - 7, x + 6):                          # shell tips rising above the rim.
        c.rect(tx, top - 3, tx + 1, top, SHELL)        # without these it is just a bowl
        c.rect(tx, top - 4, tx + 1, top - 4, INK)
    c.d.point([(x - 7, top - 3), (x + 7, top - 3)], SHELL_HI)

    if x >= STATIONS[2]:                         # filled — sits proud of the rim
        c.rect(x - 5, top - 2, x + 5, top, LETTUCE)
        c.d.point([(x - 3, top - 3), (x + 1, top - 3), (x + 4, top - 2)], TOMATO)
        c.d.point([(x - 1, top - 2), (x + 3, top - 1)], SHELL_HI)

    if x >= STATIONS[3]:                         # wrapped in paper
        c.d.polygon([(x - 9, b), (x - 6, top - 4), (x - 1, top - 3), (x - 3, b)],
                    fill=PAPER, outline=INK)


# ── scenery ────────────────────────────────────────────────────────────────
def draw_floor(c: Canvas):
    c.rect(0, FLOOR_Y, W, H, BG_DARK)


def draw_belt(c: Canvas, phase: int):
    """Drawn after the workers, so it occludes their legs and they read as behind it."""
    c.rect(0, BELT_Y, W, BELT_Y + 2, STEEL_MID)
    c.rect(0, BELT_Y, W, BELT_Y, STEEL_HI)
    for x in range(-TREAD, W + TREAD, TREAD):    # belt slats scroll with the phase
        sx = x + phase % TREAD
        c.rect(sx, BELT_Y, sx + 1, BELT_Y + 2, STEEL_LO)
        c.rect(sx + 2, BELT_Y, sx + 2, BELT_Y + 2, STEEL_HI)
    c.rect(0, BELT_Y + 3, W, BELT_Y + 3, INK)
    c.rect(0, BELT_Y + 4, W, BELT_Y + 7, STEEL_DK)
    for x in range(1, W, 8):                     # rollers
        c.d.ellipse([x, BELT_Y + 4, x + 4, BELT_Y + 8], fill=STEEL_LO, outline=STEEL_DK)
    for x in (20, 90, 160, 228):                 # legs down to the floor
        c.rect(x, BELT_Y + 8, x + 2, FLOOR_Y + 3, STEEL_DK)


def worker(c: Canvas, x: int, bob: int):
    """Head and shoulders only — that is all that clears the belt, and a full figure
    at this scale just reads as a vase."""
    y = 20 + bob
    c.rect(x - 4, y, x + 3, y, EMBER)            # cap brim
    c.rect(x - 3, y - 2, x + 2, y - 1, EMBER)    # cap crown
    c.rect(x - 3, y + 1, x + 2, y + 4, SKIN)     # face
    c.d.point([(x - 2, y + 2), (x + 1, y + 2)], INK)
    c.rect(x - 5, y + 5, x + 4, y + 11, KHAKI)   # shoulders and chest
    c.rect(x - 5, y + 5, x + 4, y + 5, (236, 228, 160))
    c.rect(x - 1, y + 6, x, y + 11, (196, 186, 112))   # collar / shirt seam
    c.rect(x - 6, y + 7, x - 6, y + 10, SKIN)          # arms
    c.rect(x + 5, y + 7, x + 5, y + 10, SKIN)


def near(phase: int, sx: int):
    """0..1, how close the nearest taco is to this station. Periodic in the phase."""
    best = STATION_GAP
    for k in range(-2, 9):
        best = min(best, abs((phase + k * STATION_GAP) - sx))
    return max(0.0, 1.0 - best / 13.0)


def draw_machines_back(c: Canvas, phase: int):
    """Everything behind the tacos."""
    s1, s2, s3, s4, s5 = STATIONS

    # 1 — crate of discs tipping onto a ramp that runs down to the belt
    tilt = int(2 * near(phase, s1))
    c.d.polygon([(s1 - 22, 33), (s1 - 8, 33), (s1 + 2, BELT_Y - 1), (s1 - 14, BELT_Y - 1)],
                fill=STEEL_MID, outline=INK)                  # chute
    c.d.line([(s1 - 20, 34), (s1 - 12, BELT_Y - 2)], fill=STEEL_HI)
    c.d.line([(s1 - 10, 34), (s1 + 0, BELT_Y - 2)], fill=STEEL_LO)
    c.box(s1 - 26, 20 + tilt, s1 - 10, 32 + tilt, CRATE)      # crate
    c.rect(s1 - 25, 21 + tilt, s1 - 11, 22 + tilt, CRATE_HI)
    c.rect(s1 - 25, 26 + tilt, s1 - 11, 26 + tilt, CRATE_HI)
    for i in range(3):                                        # discs waiting inside
        c.d.ellipse([s1 - 23 + i * 5, 28 + tilt, s1 - 19 + i * 5, 30 + tilt],
                    fill=DOUGH, outline=INK)
    c.d.ellipse([s1 - 12, 33 + tilt, s1 - 6, 35 + tilt], fill=DOUGH, outline=INK)

    # 2 — the press: heavy columns, solid crown, ram on a shaft
    c.rect(s1 + 0, 0, s1, 0, BG)                              # (no-op, keeps s1 used)
    c.box(s2 - 15, 8, s2 + 15, 16, STEEL)                     # crown
    c.rect(s2 - 13, 10, s2 + 13, 11, STEEL_HI)
    c.rect(s2 - 13, 14, s2 + 13, 15, STEEL_LO)
    for cx in (s2 - 14, s2 + 10):                             # columns down to the belt
        c.box(cx, 16, cx + 4, BELT_Y - 1, STEEL_LO)
        c.rect(cx + 1, 17, cx + 1, BELT_Y - 2, STEEL)
    c.rect(s2 - 13, BELT_Y - 2, s2 + 13, BELT_Y - 1, STEEL_DK)  # anvil on the belt

    # 3 — hoppers on a gantry
    c.rect(s3 - 22, 27, s3 + 22, 29, STEEL_DK)
    for i, col in enumerate((TOMATO, LETTUCE, SHELL_HI)):
        hx = s3 - 13 + i * 13
        c.box(hx - 5, 12, hx + 5, 20, STEEL)
        c.rect(hx - 4, 13, hx + 4, 15, col)
        c.d.polygon([(hx - 5, 20), (hx + 5, 20), (hx + 1, 27), (hx - 1, 27)],
                    fill=STEEL_MID, outline=INK)

    # 4 — wrapper housing, straddling the belt
    c.rect(s4 - 15, 18, s4 - 12, BELT_Y - 1, STEEL_LO)
    c.rect(s4 + 12, 18, s4 + 15, BELT_Y - 1, STEEL_LO)
    c.box(s4 - 17, 14, s4 + 17, 24, STEEL)
    c.rect(s4 - 12, 17, s4 - 4, 21, STEEL_DK)
    c.rect(s4 + 4, 17, s4 + 12, 21, STEEL_DK)

    # 5 — an open box at the end, already half full of wrapped tacos
    bx = s5 + 4                                                  # keeps the flaps in frame
    c.rect(bx - 12, BELT_Y - 6, bx + 12, BELT_Y + 1, CRATE_HI)     # inside back wall
    for i in range(3):                                             # packed, still wrapped
        c.d.polygon([(bx - 9 + i * 8, BELT_Y + 1), (bx - 7 + i * 8, BELT_Y - 5),
                     (bx - 3 + i * 8, BELT_Y - 5), (bx - 4 + i * 8, BELT_Y + 1)],
                    fill=PAPER, outline=INK)
    c.box(bx - 13, BELT_Y + 1, bx + 13, BELT_Y + 11, CRATE)        # front panel
    c.rect(bx - 11, BELT_Y + 4, bx + 11, BELT_Y + 5, CRATE_HI)
    c.d.polygon([(bx - 13, BELT_Y - 6), (bx - 19, BELT_Y - 9),     # open flaps
                 (bx - 19, BELT_Y - 1), (bx - 13, BELT_Y + 1)], fill=CRATE, outline=INK)
    c.d.polygon([(bx + 13, BELT_Y - 6), (bx + 18, BELT_Y - 9),
                 (bx + 18, BELT_Y - 1), (bx + 13, BELT_Y + 1)], fill=CRATE, outline=INK)


def draw_machines_front(c: Canvas, phase: int):
    """The moving parts that pass in front of the tacos."""
    s1, s2, s3, s4, s5 = STATIONS

    drop = int(8 * near(phase, s2))               # ram comes down as a disc arrives
    c.rect(s2 - 3, 16, s2 + 2, 23 + drop, STEEL_HI)
    c.rect(s2 - 2, 16, s2 - 2, 23 + drop, STEEL)
    c.box(s2 - 12, 23 + drop, s2 + 12, 29 + drop, STEEL_MID)
    c.rect(s2 - 10, 25 + drop, s2 + 10, 26 + drop, STEEL_HI)
    c.rect(s2 - 10, 28 + drop, s2 + 10, 28 + drop, STEEL_DK)

    if near(phase, s3) > 0.3:                     # filling falling from the hoppers
        for i, col in enumerate((TOMATO, LETTUCE, SHELL_HI)):
            hx = s3 - 13 + i * 13
            for j in range(3):
                fy = 29 + ((phase * 2 + j * 4 + i * 3) % (BELT_Y - 31))
                c.d.point([(hx, fy), (hx + 1, fy)], col)

    close = int(6 * near(phase, s4))              # wrapper arms fold the paper in
    c.d.polygon([(s4 - 13 + close, 25), (s4 - 4 + close, 27),
                 (s4 - 4 + close, BELT_Y - 4), (s4 - 13 + close, BELT_Y - 6)],
                fill=PAPER, outline=INK)
    c.d.polygon([(s4 + 13 - close, 25), (s4 + 4 - close, 27),
                 (s4 + 4 - close, BELT_Y - 4), (s4 + 13 - close, BELT_Y - 6)],
                fill=PAPER, outline=INK)


def frame(i: int) -> Image.Image:
    phase = round(i * STATION_GAP / FRAMES)
    c = Canvas()
    draw_floor(c)
    draw_machines_back(c, phase)
    for x in (52, 104, 156, 208):                       # workers stand between stations
        worker(c, x, (phase + x) % 4 // 2)   # period must divide STATION_GAP
    draw_belt(c, phase)                                 # occludes the workers' legs
    for k in range(-1, W // STATION_GAP + 3):           # tacos, one station-gap apart
        draw_taco(c, phase + k * STATION_GAP)
    draw_machines_front(c, phase)                       # ram, filling, wrapper arms
    return c.im.resize((W * SCALE, H * SCALE), Image.NEAREST)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", action="store_true", help="write frame 0 as a PNG")
    ap.add_argument("--fps", type=int, default=12)
    a = ap.parse_args()

    frames = [frame(i) for i in range(FRAMES)]
    if a.still:
        out = ROOT / "assets" / "banner-drawn.png"
        frames[0].convert("P", palette=Image.ADAPTIVE, colors=32).save(out, optimize=True)
        print(f"-> {out.relative_to(ROOT)}")
        return

    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=32) for f in frames]
    out = ROOT / "assets" / "banner.gif"
    pal[0].save(out, save_all=True, append_images=pal[1:], loop=0,
                duration=round(1000 / a.fps), optimize=True, disposal=2)
    kb = out.stat().st_size // 1024
    print(f"-> {out.relative_to(ROOT)}  {frames[0].size[0]}x{frames[0].size[1]}  "
          f"{FRAMES} frames  {a.fps}fps  {kb} KB")


if __name__ == "__main__":
    main()
