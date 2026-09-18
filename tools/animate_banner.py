#!/usr/bin/env python3
"""
Animate the static banner itself.

    python3 tools/animate_banner.py            # -> assets/banner-anim.gif
    python3 tools/animate_banner.py --debug    # also writes the clean plate + layers

Earlier versions animated a separately generated "empty belt" plate. It was a weaker
picture than the banner: an empty closed bin, a press whose head sat beside its own
table, sparser and smaller tacos. This version uses assets/banner.png as the base, so
everything the static has is kept:

  * the bin stays full — the stack inside, the one sliding out and the one leaning at
    the mouth are left exactly as drawn, and new tortillas are dealt out from behind
    the leaning one
  * the press is the static's coherent press. Its drawn pose (head down on a squashed
    disc) becomes the bottom of the stroke; the head is lifted out and raised
  * tacos are native size, 140px apart, as in the static

To free the belt, every taco is keyed out and the belt SURFACE is rebuilt rather than
inpainted: each row is flat in x, so a row median gives its colour, and the slats are
redrawn procedurally — which is also what finally lets the belt scroll.

THE LOOP. Everything is a pure function of the phase (0..SPACING). A taco's place and
look depend only on distance travelled and tacos sit exactly SPACING apart, so after
one SPACING of travel taco k is where, and looks like, taco k+1 was at frame 0. Every
other cycle (slats 35, grains 140, workers 70) divides SPACING. Checked on every run
by rendering phase == SPACING and diffing it against phase 0.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "assets" / "art"
SRC = ROOT / "assets" / "banner.png"

W, H = 2064, 512
BASELINE = 362
SPACING = 140             # gap between tacos == travel per loop
FRAMES = 14               # 10px per frame; ~14 textured tacos move every frame, so
                          # frame count is what the file size actually scales with
SLAT = 35                 # divides SPACING; step 10 < SLAT/2 so it never aliases backwards

# ── the path ────────────────────────────────────────────────────────────────
SPAWN_X = 160             # inside the bin, hidden behind its wall and the stack
LEAN_X, LEAN_BASE = 232, 357   # where the static drew a tortilla leaning at the mouth
SETTLE_X = 292            # flat on the belt from here
CHUTE_SLOPE = 1.18        # the bin's own tilt, so it slides out along the bin
PRESS_X, PRESS_HOLD, PRESS_RAMP, HEAD_UP = 643, 24, 42, 22
FILL_FROM, FILL_TO = 985, 1180
WRAP_X = 1466             # behind the wrapper's centre column
DROP_FROM, DROP_TO = 1822, 1866     # tips off the belt over the box's opening
DROP_BASE, DROP_SCALE = 478, 0.6    # ends behind the front wall, shrunk to fit the opening
BOX_FLOOR = 468                     # nothing is drawn below the box itself

NOZZLES = [(1012, (176, 52, 30)), (1085, (112, 176, 44)), (1162, (250, 200, 48))]
NOZZLE_Y = 268

# ── geometry of the static, read off gridded crops ──────────────────────────
BELT_ROWS = (312, 373)                      # back-edge ink through the surface
BELT_X = (272, 2030)
TUNNEL = (972, 281, 1189, 312)              # dark recess under the nozzles
PRESSED_BOX = (596, 319, 692, 358)          # the squashed disc drawn in the press
HEAD_BOX = (538, 213, 741, 320)
POST_COLS = [(546, 566), (713, 733)]
LEFT_BLADE = [(1376, 272), (1429, 309), (1429, 366), (1406, 366), (1350, 308)]
# The static's right blade is drawn wrapped round a taco that is no longer there, so
# keying it leaves rags. It is erased and redrawn clean, to match the left one.
RIGHT_BLADE_OLD = (1504, 268, 1618, 362)
RIGHT_BLADE = [(1604, 283), (1609, 291), (1540, 352), (1504, 366), (1504, 322), (1528, 305)]
# The wrapper's moving parts. Each blade is [free vertices..., then the two on the
# column]; the free ones swing about the pivot as a taco passes behind the column.
BLADES = {
    "left":  dict(free=[(1406, 366), (1350, 308), (1376, 272)], fixed=[(1429, 309), (1429, 366)],
                  pivot=(1429, 338), swing=-0.17),
    "right": dict(free=[(1528, 305), (1604, 283), (1609, 291), (1540, 352)],
                  fixed=[(1504, 366), (1504, 322)], pivot=(1504, 344), swing=0.12),
}
PLUNGER_BOX, PLUNGER_TRAVEL = (1471, 181, 1511, 246), 6
LIGHT_BOX = (1452, 376, 1470, 394)
LEAN_BOX = (193, 281, 271, 359)             # the leaning tortilla, lifted out to tumble
BELT_START = (224, 313, 0.746)              # belt's slanted left end: x = 224 - (y-313)*k
FRONT_RECTS = [
    (546, 287, 566, 377), (713, 287, 733, 377),     # press posts below the head
    (1428, 292, 1504, 452),                         # wrapper centre column
    (1697, 285, 1769, 452),                         # arch, front pillar
]
WRAPPER_TOP = (1392, 160, 1566, 300)
BOX_REGION = (1805, 376, 1926, 470)
BOX_FRONT_Y = 426                   # front wall starts here; above it is the opening
MOUTH_AT, MOUTH_SCALE = (157, 247), 0.9     # the tortilla sitting in the bin's mouth
MOUTH_LINE = ((230, 245), (197, 310))       # the bin's open end, far rim to near rim
RIM = (137, 238, 1.2)               # bin's near rim: y = 238 + (x - 137) * 1.2
WORKERS = {"w1": (445, 205, 516, 312), "w2": (855, 205, 936, 312),
           "w3": (1300, 205, 1376, 312)}
PACKER_BOX = (1765, 326, 1840, 396)
# Stretches where rows above the belt edge are open sky in the static. A taco's top
# pokes up into them, and its paper shading is grey — invisible to a colour key — so
# here EVERYTHING that is not sky goes, not just what looks like food.
SKY_ZONES = [(272, 445), (516, 538), (741, 855), (1244, 1300), (1594, 1697), (1882, 2040)]
SKY_PATCH = (471, 304, 497, 313)            # disc top showing between worker 1's forearms
LIGHT_KEY = (1772, 288, 1882, 312)          # wrapped-taco paper in front of the arch

PROTECT = [                                         # never treated as tacos
    (0, 0, 272, H),                                 # the bin and its tortillas
    (445, 205, 516, 304), (446, 285, 471, 316), (496, 285, 514, 318),     # worker 1 + arms
    (855, 205, 948, 314), (1300, 205, 1376, 312),   # workers 2, 3
    (945, 0, 1240, 272),                            # hopper contents and windows
    (960, 365, 1216, H),                            # control panel
    (1805, 376, 1930, H),                           # the box
]
PACKER_RECT = (1765, 326, 1842, H)          # protected except where it is white paper


# ── helpers ─────────────────────────────────────────────────────────────────
def chan(a):
    return a[..., 0].astype(int), a[..., 1].astype(int), a[..., 2].astype(int)


def is_navy(a):
    r, g, b = chan(a)
    return (b > r + 38) & (b > 85)


def is_grey(a):
    r, g, b = chan(a)
    return (abs(r - g) < 26) & (abs(g - b) < 26) & (r > 88) & (r < 216)


def is_ink(a):
    r, g, b = chan(a)
    return (r < 80) & (g < 80) & (b < 80)


def is_light(a):
    r, g, b = chan(a)
    return (abs(r - g) < 26) & (abs(g - b) < 26) & (r > 178)


def rect_mask(box):
    x0, y0, x1, y1 = box
    m = np.zeros((H, W), bool)
    m[y0:y1, x0:x1] = True
    return m


def poly_mask(poly):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon(poly, fill=255)
    return np.asarray(m) > 0


def dilate(m, n=1):
    for _ in range(n):
        g = m.copy()
        g[1:] |= m[:-1]; g[:-1] |= m[1:]; g[:, 1:] |= m[:, :-1]; g[:, :-1] |= m[:, 1:]
        m = g
    return m


def cut(a, mask):
    out = np.zeros((H, W, 4), np.uint8)
    out[..., :3] = a
    out[..., 3] = np.where(mask, 255, 0)
    return Image.fromarray(out, "RGBA")


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def snap_palette(rgb, dist=26, max_colors=64, bits=5):
    """Population-weighted leader clustering, not median cut: PIL's adaptive palette
    allocates slots by pixel count, so flat areas eat the budget and the oranges go
    brown. A colour is kept as a leader or snapped to a more popular one in `dist`."""
    a = np.asarray(rgb).astype(np.uint8)
    binned = a >> (8 - bits)
    keys = (binned[..., 0].astype(np.int32) << (2 * bits)) | \
           (binned[..., 1].astype(np.int32) << bits) | binned[..., 2].astype(np.int32)
    uniq, inv, cnt = np.unique(keys.ravel(), return_inverse=True, return_counts=True)
    flat = a.reshape(-1, 3).astype(np.float64)
    reps = np.stack([np.bincount(inv, weights=flat[:, c], minlength=len(uniq)) / cnt
                     for c in range(3)], axis=1)
    leaders, assign = [], np.empty(len(uniq), np.int32)
    for i in np.argsort(-cnt):
        c = reps[i]
        if leaders:
            d = np.sqrt(((np.array(leaders) - c) ** 2).sum(1))
            j = int(d.argmin())
            if d[j] <= dist:
                assign[i] = j
                continue
        leaders.append(c)
        assign[i] = len(leaders) - 1
    leaders = np.array(leaders)
    if len(leaders) > max_colors:
        weight = np.bincount(assign, weights=cnt, minlength=len(leaders))
        keep = np.argsort(-weight)[:max_colors]
        d = np.sqrt(((leaders[:, None, :] - leaders[None, keep, :]) ** 2).sum(2))
        assign = keep[d.argmin(1)][assign]
    out = np.clip(leaders[assign][inv].reshape(a.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(out)


# ── scene preparation ───────────────────────────────────────────────────────
def prepare():
    orig = np.asarray(Image.open(SRC).convert("RGB")).copy()
    a = orig.copy()
    navy, grey, ink = is_navy(orig), is_grey(orig), is_ink(orig)
    ys, xs = np.mgrid[0:H, 0:W]

    left_blade = poly_mask(LEFT_BLADE)
    old_blade = rect_mask(RIGHT_BLADE_OLD) & (is_light(orig) | ink) \
        & ((ys >= 304) | (xs >= 1562))
    right_blade = poly_mask(RIGHT_BLADE)

    # the leaning tortilla: its body is one connected blob of food colour, and the
    # keyline is whatever ink hugs it (the box also holds bin and belt-edge ink)
    body = rect_mask(LEAN_BOX) & ~navy & ~grey & ~ink
    lab = np.zeros((H, W), bool); stack = [(330, 235)]
    while stack:
        y, x = stack.pop()
        if 0 <= y < H and 0 <= x < W and body[y, x] and not lab[y, x]:
            lab[y, x] = True
            stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    # its keyline is ~3px, so reach 4 — but not into the bin's own corner outline
    lean = lab | (dilate(lab, 4) & ink & rect_mask(LEAN_BOX)
                  & ~((xs < 197) & (ys < 312)))
    solid = np.zeros((H, W), bool)                   # machine parts items never touch
    for r in FRONT_RECTS:
        solid |= rect_mask(r)
    protect = solid.copy()
    for r in PROTECT:
        protect |= rect_mask(r)
    protect |= rect_mask(PACKER_RECT) & ~is_light(orig)   # a taco's paper hides behind him

    # 1. key out every taco: coloured (not sky, not machine grey, not ink) pixels in
    #    the band the line occupies, then pull in the keyline that hugs them
    band = rect_mask((272, 262, 2040, 373))
    item = band & ~navy & ~grey & ~ink & ~protect
    item &= ~(left_blade & is_light(orig))           # the blade is white, not paper
    pressed = rect_mask(PRESSED_BOX) & ~navy & ~grey & ~ink
    item |= pressed
    item |= rect_mask(LIGHT_KEY) & is_light(orig) & ~protect
    item |= rect_mask(PACKER_RECT) & is_light(orig) & (ys < 376)
    sky_force = rect_mask(SKY_PATCH)
    for zx0, zx1 in SKY_ZONES:
        sky_force |= rect_mask((zx0, 250, zx1, BELT_ROWS[0])) & ~navy
    # behind the leaning tortilla is open sky everywhere except the belt's own start;
    # nearest-neighbour fill dragged the bin's floor shadow across it instead
    sx, sy, sk = BELT_START
    sky_force |= lean & ~((ys >= BELT_ROWS[0]) & (xs > (sx - (ys - sy) * sk)))
    sky_force |= old_blade & (ys < BELT_ROWS[0]) & (xs >= 1590)
    # the left blade comes out too, so both can swing. Its keyline is only taken where
    # it is its own (x < 1398); further right it merges with the machine arm's outline
    lb_gone = left_blade | (dilate(left_blade, 3) & ink & ~protect & (xs < 1398)
                            & (xs > 1372))
    sky_force |= lb_gone & (ys < BELT_ROWS[0]) & (xs > 1372)
    erase = item | (dilate(item, 2) & ink & ~protect) | sky_force | lean | old_blade | lb_gone

    # 2. rebuild the belt surface from row medians. Flat in x, so the median of the
    #    machine-free grey in a row IS that row's colour; slats are redrawn later
    y0, y1 = BELT_ROWS
    machines = protect | rect_mask((528, 0, 748, H)) \
        | rect_mask((1376, 364, 1590, H))
    belt = rect_mask((BELT_X[0], y0, BELT_X[1], y1)) & ~machines & (~navy | erase)
    # the belt's own left end was hidden behind the leaning tortilla: rebuild it
    sx, sy, sk = BELT_START
    past_start = xs > (sx - (ys - sy) * sk)
    belt |= rect_mask((180, y0, BELT_X[0], y1)) & past_start & (lean | grey)
    belt_rows = {}
    for y in range(y0, y1):
        ref = orig[y][belt[y] & ~erase[y]]
        belt_rows[y] = np.median(ref, axis=0) if len(ref) else np.array([140, 140, 140])
        a[y, belt[y]] = belt_rows[y]

    # 3. everything else that was under a taco
    rest = erase & ~belt
    tx0, ty0, tx1, ty1 = TUNNEL
    tun = orig[ty0:ty1, tx0:tx1]
    tun_col = np.median(tun[(tun[..., 0] > 40) & (tun[..., 0] < 95)], axis=0)
    a[rect_mask(TUNNEL)] = tun_col                   # also clears the painted streams
    rest &= ~rect_mask(TUNNEL)
    # the squashed disc AND its keyline: left alone, the outline stays behind as a dark
    # ring on the platen. Rows under 325 are the platen's own top edge, so keep those.
    a[pressed | (rect_mask(PRESSED_BOX) & ink & (ys >= 325))] = orig[364, 640]
    rest &= ~rect_mask(PRESSED_BOX)
    navy_now = is_navy(a)
    for y in np.unique(np.where(sky_force)[0]):
        ref = a[y][navy_now[y] & ~erase[y]]
        a[y, sky_force[y]] = np.median(ref, axis=0) if len(ref) else (29, 70, 128)
    rest &= ~sky_force
    for y in np.unique(np.where(rest)[0]):
        row_ok = ~erase[y]
        for x in np.where(rest[y])[0]:
            l = x - 1
            while l > 0 and not row_ok[l]:
                l -= 1
            r = x + 1
            while r < W - 1 and not row_ok[r]:
                r += 1
            a[y, x] = a[y, l] if (x - l) <= (r - x) else a[y, r]
    d = ImageDraw.Draw(im_a := Image.fromarray(a))
    d.line([(sx, sy), (round(sx - (y1 - 1 - sy) * sk), y1 - 1)], fill=(1, 1, 1), width=3)
    a = np.asarray(im_a).copy()
    clean = a.copy()

    # 4. the press head, lifted out. Behind it: sky, the two posts (hidden where the
    #    lobes wrap them, so extend the post row from just above) and the belt edge
    head = rect_mask(HEAD_BOX) & ~is_navy(clean)
    for c0, c1 in POST_COLS:
        head &= ~((xs >= c0) & (xs < c1) & ((ys < 253) | (ys >= 288)))
    head_sprite = cut(clean, head)
    sky_rows = {y: np.median(clean[y][is_navy(clean)[y]], axis=0) for y in range(H)
                if is_navy(clean)[y].any()}
    for y in np.unique(np.where(head)[0]):
        a[y, head[y]] = belt_rows[y] if y >= y0 else sky_rows.get(y, (29, 70, 128))
    for c0, c1 in POST_COLS:
        col = head & (xs >= c0) & (xs < c1)
        rows = np.repeat(clean[251:252], H, axis=0)
        a[col] = rows[col]

    # 4b. the wrapper's plunger. It only ever moves DOWN, so all it uncovers is a few
    #     rows of housing at its top — copied from the same rows just to its left,
    #     which carries the housing's horizontal trim lines across correctly
    plunger = rect_mask(PLUNGER_BOX) & ~((xs >= 1505) & (ys >= 231))
    plunger_sprite = cut(clean, plunger)
    top = plunger & ~np.roll(plunger, PLUNGER_TRAVEL, axis=0)
    ty, tx = np.where(top)
    a[ty, tx] = clean[ty, 1464]
    socket = cut(clean, rect_mask((1462, 246, 1512, 268)) | rect_mask((1505, 231, 1536, 262)))

    # 5. workers stand against sky: lift out, repaint sky, redraw with a dip
    workers = {}
    for name, box in WORKERS.items():
        m = rect_mask(box) & ~is_navy(clean)
        if name == "w2":
            m &= ~((xs >= 931) & (ys < 262))          # the lever knob stays put
        if name == "w3":
            m &= ~dilate(left_blade, 2)
        workers[name] = cut(clean, m)
        grown = dilate(m)
        for y in np.unique(np.where(grown)[0]):
            a[y, grown[y]] = sky_rows.get(y, (29, 70, 128))

    pk = rect_mask(PACKER_BOX) & ~is_navy(clean) & ~is_grey(clean)
    packer = cut(clean, pk)
    exposed = pk & ~np.roll(pk, 2, axis=0)
    patch = np.zeros((H, W, 4), np.uint8)
    ey, ex = np.where(exposed)
    patch[ey, ex, :3] = clean[ey - 4, ex]
    patch[ey, ex, 3] = 255

    # 6. what stands in front of the line
    front = solid.copy()
    front |= rect_mask((0, 0, 198, 380)) & ~is_navy(clean)           # the bin
    front |= rect_mask(WRAPPER_TOP) & ~is_navy(clean) & ~plunger
    front |= rect_mask((546, 193, 566, 253)) | rect_mask((713, 193, 733, 253))
    # The box is NOT all foreground. A taco drops in front of the back flap and the
    # opening, and behind the front wall, the right-hand flap and the packer's hands —
    # with the whole box in front it simply fell behind the box.
    box = rect_mask(BOX_REGION) & ~navy & ~grey
    box = rect_mask(BOX_REGION) & ~dilate(~dilate(box, 3), 3)
    front |= box & ((ys >= BOX_FRONT_Y) | (xs >= 1884) | ((xs <= 1848) & (ys >= 400)))
    front_layer = cut(clean, front)
    # The tortilla in the bin's mouth was half hidden by the leaning one, so with that
    # gone it was left as a wedge with a straight cut edge. Give it a whole body — the
    # leaning tortilla's own sprite, slightly smaller — tucked behind the near wall.
    lys, lxs = np.where(lean)
    tilt = cut(orig, lean).crop((lxs.min(), lys.min(), lxs.max() + 1, lys.max() + 1))
    mouth = tilt.resize((round(tilt.width * MOUTH_SCALE), round(tilt.height * MOUTH_SCALE)),
                        Image.NEAREST)
    front_layer.alpha_composite(mouth, MOUTH_AT)
    rx, ry, rk = RIM
    wall = rect_mask((100, 225, 232, 335)) & (ys > ry + (xs - rx) * rk - 2) & ~is_navy(clean)
    front_layer.alpha_composite(cut(clean, wall))

    sprites = {n: Image.open(ART / f"{n}.png").convert("RGBA")
               for n in ("disc", "shell", "filled", "wrapped")}
    pm = dilate(pressed, 1) & rect_mask(PRESSED_BOX) & (pressed | ink)
    pys, pxs = np.where(pm)
    sprites["tilt"] = tilt
    sprites["pressed"] = cut(orig, pm).crop((pxs.min(), pys.min(),
                                             pxs.max() + 1, pys.max() + 1))

    return dict(plate=Image.fromarray(a).convert("RGBA"), clean=clean, head=head_sprite,
                workers=workers, packer=packer,
                packer_patch=Image.fromarray(patch, "RGBA"), front=front_layer,
                sprites=sprites, belt=belt, belt_rows=belt_rows,
                plunger=plunger_sprite, socket=socket)


# ── per-frame ───────────────────────────────────────────────────────────────
def travels(phase):
    return [phase + k * SPACING for k in range(-1, W // SPACING + 2)
            if SPAWN_X <= phase + k * SPACING <= DROP_TO]


def draw_slats(f, phase, sc):
    """Slats lean like the static's (top edge further right) and ride with the belt."""
    a = np.asarray(f).copy()
    y0, y1 = BELT_ROWS
    for y in range(y0 + 4, y1 - 1):
        xs = np.arange(BELT_X[0] - SLAT, BELT_X[1] + SLAT)
        on = ((xs - phase + 0.37 * (y - y0)).astype(int) % SLAT) < 2
        cols = xs[on]
        cols = cols[(cols >= 0) & (cols < W)]
        cols = cols[sc["belt"][y, cols]]
        a[y, cols, :3] = np.clip(sc["belt_rows"][y] - 24, 0, 255)
    return Image.fromarray(a, "RGBA")


def draw_taco(f, s, sprites):
    x = s

    def put(img, base=BASELINE):
        f.alpha_composite(img, (x - img.width // 2, base - img.height))

    if s < SETTLE_X:
        tilt = sprites["tilt"]
        if s <= LEAN_X:                            # sliding out of the bin along its tilt
            base = round(LEAN_BASE - (LEAN_X - s) * CHUTE_SLOPE)
            # Only what has passed the plane of the bin's mouth is drawn. Without this
            # the tortilla's top edge showed in the gap between the mouth tortilla and
            # the rim while it was still inside — a fin that popped in, then slid out.
            (ax, ay), (bx, by) = MOUTH_LINE
            arr = np.asarray(tilt).copy()
            jj, ii = np.mgrid[0:tilt.height, 0:tilt.width]
            px, py = x - tilt.width // 2 + ii, base - tilt.height + jj
            inside = (bx - ax) * (py - ay) - (by - ay) * (px - ax) >= 0
            arr[..., 3] = np.where(inside, 0, arr[..., 3])
            put(Image.fromarray(arr, "RGBA"), base=base)
        else:                                      # tipping over flat onto the belt
            t = smooth((s - LEAN_X) / (SETTLE_X - LEAN_X))
            flat = sprites["disc"]
            w = round(tilt.width + (flat.width - tilt.width) * t)
            h = round(tilt.height + (flat.height - tilt.height) * t)
            put(tilt.resize((w, h), Image.NEAREST),
                base=round(LEAN_BASE + (BASELINE - LEAN_BASE) * t))
    elif abs(s - PRESS_X) <= PRESS_HOLD:
        put(sprites["pressed"], base=357)          # squashed, exactly as the static
    elif s < PRESS_X:
        put(sprites["disc"])
    elif s < FILL_FROM:
        put(sprites["shell"])
    elif s < FILL_TO:
        put(sprites["shell"])                      # filling wipes in, leading edge first
        full = sprites["filled"]
        cutx = round(full.width * (1 - (s - FILL_FROM) / (FILL_TO - FILL_FROM)))
        f.alpha_composite(full.crop((cutx, 0, full.width, full.height)),
                          (x - full.width // 2 + cutx, BASELINE - full.height))
    elif s < WRAP_X:
        put(sprites["filled"])
    elif s <= DROP_FROM:
        put(sprites["wrapped"])
    else:                                          # tips off the belt into the box
        t = (s - DROP_FROM) / (DROP_TO - DROP_FROM)
        img = sprites["wrapped"]
        k = 1 - (1 - DROP_SCALE) * t
        img = img.resize((round(img.width * k), round(img.height * k)), Image.NEAREST)
        base = round(BASELINE + (DROP_BASE - BASELINE) * t * t)
        if base > BOX_FLOOR:                       # never poke out under the box
            img = img.crop((0, 0, img.width, img.height - (base - BOX_FLOOR)))
            base = BOX_FLOOR
        put(img, base=base)


def head_down(ts):
    """1 while a disc is under the press (the static's own pose), 0 fully raised."""
    d = min((abs(s - PRESS_X) for s in ts), default=999)
    return smooth(1 - max(0, d - PRESS_HOLD) / PRESS_RAMP)


def draw_grains(f, phase, ts):
    """Chunks 28px apart falling 10px a frame — the step stays under half the spacing,
    or the stream reads as drifting upward. Five chunks make a 140px cycle."""
    d = ImageDraw.Draw(f)
    for nx, col in NOZZLES:
        if min((abs(s - nx) for s in ts), default=999) > 48:
            continue
        dark = tuple(int(c * 0.62) for c in col)
        for j in range(5):
            y = NOZZLE_Y - 8 + (phase + j * 28) % 140
            if y < NOZZLE_Y or y > BASELINE - 56:
                continue
            gx = nx + (-5, 3, -2, 4, 0)[j]
            d.rectangle([gx - 5, y, gx + 4, y + 8], fill=dark + (255,))
            d.rectangle([gx - 4, y + 1, gx + 3, y + 6], fill=col + (255,))


def wrap_fold(ts):
    """0..1 — how far the wrapper has closed on the taco passing behind its column."""
    d = min((abs(s - WRAP_X) for s in ts), default=999)
    return smooth(1 - max(0, d - 10) / 40)


def draw_blades(f, fold):
    """Both paper blades, swung down about their hinge on the column. Drawn rather than
    cut from the static: its right blade was wrapped round a taco that is gone, and a
    cut-out cannot rotate without tearing anyway. White, a shaded lower edge, and the
    same heavy keyline as everything else."""
    d = ImageDraw.Draw(f)
    for b in BLADES.values():
        px, py = b["pivot"]
        th = b["swing"] * fold
        c, sn = np.cos(th), np.sin(th)
        free = [(round(px + (x - px) * c - (y - py) * sn),
                 round(py + (x - px) * sn + (y - py) * c)) for x, y in b["free"]]
        poly = free + b["fixed"]
        d.polygon(poly, fill=(243, 243, 243, 255))
        # shade a band along the lowest free edge, pulled in toward the centroid
        cx = sum(x for x, _ in poly) / len(poly); cy = sum(y for _, y in poly) / len(poly)
        low = sorted(free, key=lambda v: -v[1])[:2]
        inner = [(round(x + (cx - x) * 0.28), round(y + (cy - y) * 0.28)) for x, y in low]
        d.polygon(low + inner[::-1], fill=(211, 211, 211, 255))
        d.line(free + [b["fixed"][0]], fill=(1, 1, 1, 255), width=3, joint="curve")
        d.line([b["fixed"][-1], free[0]], fill=(1, 1, 1, 255), width=3)


def build_frame(i, sc):
    phase = round(i * SPACING / FRAMES)
    ts = travels(phase)
    down = head_down(ts)
    f = draw_slats(sc["plate"].copy(), phase, sc)

    def layer(img, dy=0):
        if dy:
            moved = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            moved.paste(img, (0, dy))
            img = moved
        f.alpha_composite(img)

    wk = sc["workers"]
    layer(wk["w1"], dy=2 if down > 0.6 else 0)                       # leans as it stamps
    layer(wk["w2"], dy=2 if any(abs(s - NOZZLES[0][0]) < 40 for s in ts) else 0)
    layer(wk["w3"], dy=2 if (phase + 35) % 70 < 35 else 0)

    for s in ts:
        draw_taco(f, s, sc["sprites"])
    draw_grains(f, phase, ts)
    layer(sc["head"], dy=-round(HEAD_UP * (1 - down)))

    fold = wrap_fold(ts)
    draw_blades(f, fold)
    layer(sc["plunger"], dy=round(PLUNGER_TRAVEL * fold))
    layer(sc["socket"])                              # plunger sinks INTO its socket
    layer(sc["front"])
    if fold > 0.4:                                   # indicator lights while it wraps
        lx0, ly0, lx1, ly1 = LIGHT_BOX
        px = f.load()
        for yy in range(ly0, ly1):
            for xx in range(lx0, lx1):
                r, g, b, _ = px[xx, yy]
                if g > r + 30 and g > b + 30:
                    px[xx, yy] = (170, 255, 90, 255)

    if any(DROP_FROM - 30 < s <= DROP_TO for s in ts):
        layer(sc["packer_patch"])
        layer(sc["packer"], dy=2)
    else:
        layer(sc["packer"])
    return f.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--colors", type=int, default=56)
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    sc = prepare()
    if a.debug:
        sc["plate"].convert("RGB").save(ART / "_debug-plate.png")
        bg = Image.new("RGBA", (W, H), (255, 0, 255, 255))
        bg.alpha_composite(sc["front"]); bg.alpha_composite(sc["head"])
        bg.convert("RGB").save(ART / "_debug-front.png")

    frames = [build_frame(i, sc) for i in range(FRAMES)]
    diff = int((np.asarray(frames[0]) != np.asarray(build_frame(FRAMES, sc))).any(2).sum())
    print(f"loop check: {diff} differing pixels at the wrap"
          + ("" if diff == 0 else "  <-- BROKEN"))

    # One shared palette + disposal=1 so PIL delta-encodes. (A transparent-index
    # variant storing only changed pixels was tried and measured no smaller: the cost
    # is the moving tacos themselves, not encoding overhead.)
    base = snap_palette(frames[0], max_colors=a.colors).convert(
        "P", palette=Image.ADAPTIVE, colors=a.colors)
    pal = [base] + [snap_palette(fr, max_colors=a.colors).quantize(palette=base,
                                                                  dither=Image.NONE)
                    for fr in frames[1:]]
    out = ROOT / "assets" / "banner-anim.gif"
    pal[0].save(out, save_all=True, append_images=pal[1:], loop=0,
                duration=round(1000 / a.fps), optimize=True, disposal=1)
    print(f"-> {out.relative_to(ROOT)}  {W}x{H}  {FRAMES} frames  {a.fps}fps  "
          f"{out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
