#!/usr/bin/env python3
"""Butterfly on the Nose -- make.fun ai-happy-01 entry (fresh authoring).

A joyful golden retriever puppy giggles in a sunny wildflower meadow
while a bright orange butterfly rests on its nose. Pure Python 3.13
standard library only: zlib + struct for the PNG encoder, math and a
seeded random for the scene. No network, no files read, no timestamps --
the same bytes come out on every run.

Scene, left to right: a low golden sun with rays in the upper left,
puffy clouds, rolling green hills with a few little trees, a meadow
full of daisies, tulips and lavender, and the puppy front and centre
with floppy ears, squeezed-shut happy eyes, tongue out, and the
butterfly on its nose. Four more butterflies drift through the air.
"""

import math
import os
import struct
import zlib
from random import Random

W = 1024
H = 1024
HORIZON = 618
RNG_SEED = 13112026

# ------------------------------------------------------------------ palette
C = {
    "sky_top": (255, 216, 142),
    "sky_mid": (255, 192, 138),
    "sky_low": (255, 178, 152),
    "sun_core": (255, 244, 196),
    "sun_rim": (255, 226, 140),
    "sun_glow": (255, 204, 105),
    "cloud": (255, 248, 230),
    "hill_far": (172, 198, 120),
    "hill_near": (126, 174, 92),
    "tree_trunk": (122, 84, 52),
    "tree_leaf": (96, 148, 74),
    "tree_leaf_lt": (126, 176, 96),
    "grass_top": (154, 200, 104),
    "grass_bot": (94, 150, 70),
    "blade_dk": (76, 130, 58),
    "blade_lt": (182, 216, 122),
    "sun_pool": (255, 222, 132),
    "shadow": (58, 96, 48),
    "fur": (234, 180, 98),
    "fur_dark": (200, 140, 60),
    "fur_cream": (250, 216, 152),
    "fur_pale": (253, 232, 184),
    "ear_in": (216, 158, 76),
    "nose": (64, 42, 30),
    "mouth": (124, 64, 48),
    "tongue": (240, 124, 134),
    "tongue_dk": (196, 84, 84),
    "eye": (94, 58, 32),
    "blush": (247, 152, 130),
    "daisy": (255, 255, 255),
    "buttercup": (255, 214, 92),
    "tulip": (245, 142, 180),
    "lavender": (188, 142, 222),
    "poppy": (255, 152, 82),
    "centre": (255, 198, 62),
    "stem": (86, 140, 66),
    "wing_orange": (255, 152, 54),
    "wing_yellow": (255, 212, 72),
    "wing_white": (255, 255, 255),
    "wing_pink": (248, 160, 196),
    "wing_edge": (72, 44, 30),
    "sparkle": (255, 244, 190),
}

FLOWER_COLOURS = [
    C["daisy"], C["buttercup"], C["tulip"], C["lavender"], C["poppy"],
]


def mix(a, b, f):
    """Linear blend of two rgb triples."""
    return tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))


def sky_colour(y):
    """Three-stop vertical sky gradient, y in [0, HORIZON)."""
    t = y / HORIZON
    if t < 0.5:
        return mix(C["sky_top"], C["sky_mid"], t * 2.0)
    return mix(C["sky_mid"], C["sky_low"], (t - 0.5) * 2.0)


# ------------------------------------------------------------------ pixmap
class Pixmap:
    """Flat RGB buffer with small scanline drawing helpers."""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def put(self, x, y, rgb, alpha=1.0):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        if alpha <= 0.0:
            return
        i = self._idx(x, y)
        if alpha >= 1.0:
            self.buf[i:i + 3] = bytes(rgb)
            return
        a = int(alpha * 256)
        ia = 256 - a
        self.buf[i] = (rgb[0] * a + self.buf[i] * ia) >> 8
        self.buf[i + 1] = (rgb[1] * a + self.buf[i + 1] * ia) >> 8
        self.buf[i + 2] = (rgb[2] * a + self.buf[i + 2] * ia) >> 8

    def span(self, y, x0, x1, rgb, alpha=1.0):
        if y < 0 or y >= self.h or alpha <= 0.0:
            return
        x0 = max(0, int(x0))
        x1 = min(self.w - 1, int(x1))
        if x1 < x0:
            return
        if alpha >= 1.0:
            n = x1 - x0 + 1
            i = self._idx(x0, y)
            self.buf[i:i + 3 * n] = bytes(rgb) * n
            return
        a = int(alpha * 256)
        ia = 256 - a
        r, g, b = rgb
        i = self._idx(x0, y)
        for _ in range(x1 - x0 + 1):
            self.buf[i] = (r * a + self.buf[i] * ia) >> 8
            self.buf[i + 1] = (g * a + self.buf[i + 1] * ia) >> 8
            self.buf[i + 2] = (b * a + self.buf[i + 2] * ia) >> 8
            i += 3

    def circle(self, cx, cy, r, rgb, alpha=1.0):
        r = int(r)
        for y in range(max(0, cy - r), min(self.h - 1, cy + r) + 1):
            dy = y - cy
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.span(y, cx - dx, cx + dx, rgb, alpha)

    def ellipse(self, cx, cy, rx, ry, rgb, alpha=1.0):
        rx, ry = int(rx), int(ry)
        if rx <= 0 or ry <= 0:
            return
        for y in range(max(0, cy - ry), min(self.h - 1, cy + ry) + 1):
            t = (y - cy) / ry
            dx = int(rx * math.sqrt(max(0.0, 1.0 - t * t)))
            self.span(y, cx - dx, cx + dx, rgb, alpha)

    def polygon(self, points, rgb, alpha=1.0):
        """Scanline fill; horizontal edges are skipped, pairs are filled."""
        pts = [(float(x), float(y)) for x, y in points]
        ymin = max(0, int(min(p[1] for p in pts)))
        ymax = min(self.h - 1, int(max(p[1] for p in pts)))
        n = len(pts)
        for y in range(ymin, ymax + 1):
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if y0 == y1:
                    continue
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.span(y, math.ceil(xs[i]), math.floor(xs[i + 1]),
                          rgb, alpha)

    def stroke(self, points, width, rgb, alpha=1.0):
        """A polyline drawn as overlapping discs (round caps/joins)."""
        rad = max(1, int(width // 2))
        for x, y in points:
            self.circle(int(x), int(y), rad, rgb, alpha)

    def radial_glow(self, cx, cy, r, rgb, peak):
        """Soft circular glow with quadratic falloff."""
        r2 = float(r * r)
        R, G, B = rgb
        for y in range(max(0, cy - r), min(self.h - 1, cy + r) + 1):
            dy = y - cy
            dy2 = dy * dy
            reach = int(math.sqrt(max(0.0, r2 - dy2)))
            for x in range(max(0, cx - reach), min(self.w - 1, cx + reach) + 1):
                dx = x - cx
                f = 1.0 - (dx * dx + dy2) / r2
                if f <= 0.0:
                    continue
                a = int(peak * f * f * 256)
                if a <= 0:
                    continue
                ia = 256 - a
                i = self._idx(x, y)
                self.buf[i] = (R * a + self.buf[i] * ia) >> 8
                self.buf[i + 1] = (G * a + self.buf[i + 1] * ia) >> 8
                self.buf[i + 2] = (B * a + self.buf[i + 2] * ia) >> 8


# ------------------------------------------------------------------ curves
def cubic_bezier(p0, p1, p2, p3, steps=18):
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        out.append((
            int(u ** 3 * p0[0] + 3 * u * u * t * p1[0]
                + 3 * u * t * t * p2[0] + t ** 3 * p3[0]),
            int(u ** 3 * p0[1] + 3 * u * u * t * p1[1]
                + 3 * u * t * t * p2[1] + t ** 3 * p3[1]),
        ))
    return out


def rotated_ellipse_points(cx, cy, rx, ry, angle_deg, steps=26):
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for k in range(steps):
        th = 2 * math.pi * k / steps
        ex, ey = rx * math.cos(th), ry * math.sin(th)
        pts.append((int(cx + ex * ca - ey * sa),
                    int(cy + ex * sa + ey * ca)))
    return pts


# ------------------------------------------------------------------ sky
def draw_sky(px):
    for y in range(HORIZON):
        px.span(y, 0, W - 1, sky_colour(y))
    # golden sun, upper left, with rays and a warm halo
    sx, sy = 185, 168
    px.radial_glow(sx, sy, 320, C["sun_glow"], 0.30)
    for k in range(12):
        ang = math.radians(k * 30.0)
        x0 = sx + int(100 * math.cos(ang))
        y0 = sy + int(100 * math.sin(ang))
        x1 = sx + int(144 * math.cos(ang))
        y1 = sy + int(144 * math.sin(ang))
        px.stroke([(x0, y0), (x1, y1)], 7, (255, 188, 78), 0.8)
    px.circle(sx, sy, 84, C["sun_rim"])
    px.circle(sx, sy, 72, C["sun_core"])
    # drifting pollen sparkles in the light
    rng = Random(RNG_SEED)
    for _ in range(26):
        px.circle(rng.randrange(40, 980), rng.randrange(30, 560),
                  rng.choice([2, 3]), C["sparkle"], 0.5)
    # puffy clouds, kept clear of the sun's rays
    for cx, cy, s in [(560, 120, 1.0), (830, 260, 0.85), (390, 300, 0.7),
                      (700, 470, 0.6), (120, 420, 0.75)]:
        for dx, dy, r in [(-70, 6, 34), (-25, -14, 42), (25, -10, 46),
                          (72, 8, 32), (0, 12, 44)]:
            px.circle(int(cx + dx * s), int(cy + dy * s), int(r * s),
                      C["cloud"], 0.34)


def draw_hills(px):
    # far hill: a broad rolling shape peeking over the horizon
    px.polygon([(0, HORIZON), (0, 596), (150, 560), (330, 600), (520, 566),
                (700, 604), (880, 570), (1024, 600), (1024, HORIZON)],
               C["hill_far"])
    # near hill, slightly lower and darker
    px.polygon([(0, HORIZON), (0, 636), (170, 610), (360, 642), (560, 614),
                (780, 646), (1024, 618), (1024, HORIZON)], C["hill_near"])
    # three little lollipop trees on the far hill
    for tx, ty, s in [(150, 566, 1.0), (905, 572, 0.9), (660, 580, 0.75)]:
        px.stroke([(tx, ty), (tx, ty - int(34 * s))], 7, C["tree_trunk"])
        px.circle(tx, ty - int(48 * s), int(26 * s), C["tree_leaf"])
        px.circle(tx - int(16 * s), ty - int(38 * s), int(18 * s),
                  C["tree_leaf_lt"])
        px.circle(tx + int(16 * s), ty - int(40 * s), int(17 * s),
                  C["tree_leaf"])


# ------------------------------------------------------------------ meadow
def draw_meadow(px):
    for y in range(HORIZON, H):
        t = (y - HORIZON) / (H - HORIZON)
        px.span(y, 0, W - 1, mix(C["grass_top"], C["grass_bot"], t))
    # warm pool of sunlight on the grass, centre-right
    px.ellipse(560, 840, 420, 120, C["sun_pool"], 0.10)
    # soft shadow where the puppy will sit
    px.ellipse(512, 992, 300, 42, C["shadow"], 0.22)


def draw_grass(px, rng):
    for _ in range(150):
        x = rng.randrange(8, 1016)
        y = rng.randrange(HORIZON + 18, 1012)
        h = rng.randrange(12, 30)
        lean = rng.randrange(-10, 11)
        col = rng.choice([C["blade_dk"], C["blade_lt"], C["grass_bot"]])
        px.polygon([(x, y), (x + lean, y - h), (x + 5, y)], col, 0.85)
        # a second blade leaning the other way makes a tuft
        px.polygon([(x + 6, y), (x + 6 - lean, y - h - 4), (x + 10, y)],
                   col, 0.8)


def draw_daisy(px, cx, cy, r, petal, centre):
    for k in range(6):
        th = 2 * math.pi * k / 6 - math.pi / 2
        px.circle(cx + int(r * 0.66 * math.cos(th)),
                  cy + int(r * 0.66 * math.sin(th)),
                  int(r * 0.46), petal)
    px.circle(cx, cy, int(r * 0.42), centre)


def draw_tulip(px, cx, cy, r, colour):
    # cup-shaped bloom on a short stem
    px.stroke([(cx, cy + int(r * 1.5)), (cx, cy + int(r * 0.4))], 4,
              C["stem"])
    px.polygon([(cx - r, cy - int(r * 0.4)), (cx - r, cy + int(r * 0.7)),
                (cx + r, cy + int(r * 0.7)), (cx + r, cy - int(r * 0.4)),
                (cx + int(r * 0.5), cy - r), (cx, cy - int(r * 0.5)),
                (cx - int(r * 0.5), cy - r)], colour)


def draw_lavender(px, cx, cy, r, colour):
    px.stroke([(cx, cy + int(r * 2.2)), (cx, cy - int(r * 0.6))], 4,
              C["stem"])
    for i in range(4):
        yy = cy - int(r * 0.5) - i * int(r * 0.42)
        px.ellipse(cx, yy, int(r * 0.42), int(r * 0.3), colour)


def draw_flowers(px, rng):
    keep_clear = (512, 830, 340)  # (cx, cy, r): the puppy's patch
    for _ in range(58):
        x = rng.randrange(28, 996)
        y = rng.randrange(HORIZON + 28, 1002)
        dx, dy = x - keep_clear[0], y - keep_clear[1]
        if dx * dx + dy * dy < keep_clear[2] ** 2:
            continue
        kind = rng.randrange(3)
        r = rng.choice([9, 11, 13, 15])
        col = rng.choice(FLOWER_COLOURS)
        if kind == 0:
            draw_daisy(px, x, y, r, col, C["centre"])
        elif kind == 1:
            draw_tulip(px, x, y, r, col)
        else:
            draw_lavender(px, x, y, r, col)
    # big soft foreground blooms framing the bottom corners
    draw_daisy(px, 92, 950, 44, C["tulip"], C["centre"])
    draw_daisy(px, 944, 934, 48, C["daisy"], C["centre"])
    draw_tulip(px, 152, 992, 30, C["buttercup"])
    draw_tulip(px, 892, 996, 32, C["lavender"])
    draw_daisy(px, 60, 830, 26, C["poppy"], C["centre"])
    draw_daisy(px, 968, 820, 26, C["buttercup"], C["centre"])


# ------------------------------------------------------------------ butterfly
def draw_butterfly(px, cx, cy, size, wing, tilt=0, open_wings=1.0):
    """Butterfly seen from above: dark-rimmed wings, pale spots, body,
    antennae. tilt rotates the whole insect; open_wings squeezes the
    upper wings for a resting pose."""
    s = size / 46.0
    a = math.radians(tilt)
    ca, sa = math.cos(a), math.sin(a)

    def place(dx, dy, rx, ry, ang):
        pts = rotated_ellipse_points(0, 0, rx, ry, ang)
        out = []
        for ex, ey in pts:
            wx, wy = dx + ex, dy + ey
            out.append((int(cx + wx * ca - wy * sa),
                        int(cy + wx * sa + wy * ca)))
        return out

    upper_h = 26 * open_wings
    for side in (-1, 1):
        # upper wing: dark rim, then coloured inner wing
        px.polygon(place(side * 17 * s, -15 * s, 22 * s, upper_h * s,
                         side * -20), C["wing_edge"], 0.95)
        px.polygon(place(side * 17 * s, -15 * s, 18 * s, upper_h * s * 0.82,
                         side * -20), wing, 0.95)
        # lower wing, smaller and rounder
        px.polygon(place(side * 15 * s, 13 * s, 16 * s, 13 * s, side * 24),
                   C["wing_edge"], 0.95)
        px.polygon(place(side * 15 * s, 13 * s, 12.5 * s, 10 * s, side * 24),
                   wing, 0.95)
        # pale spot on the upper wing
        sx = cx + int((side * 17 * s) * ca - (-15 * s) * sa)
        sy = cy + int((side * 17 * s) * sa + (-15 * s) * ca)
        px.circle(sx, sy, int(4.5 * s), C["wing_white"], 0.9)
    # body, head and two curled antennae
    px.stroke(cubic_bezier((cx, cy - 17 * s), (cx - 2 * s, cy),
                           (cx + 2 * s, cy + 8 * s), (cx, cy + 19 * s)),
              6, C["wing_edge"])
    px.circle(cx, int(cy - 17 * s), int(4 * s), C["wing_edge"])
    px.stroke(cubic_bezier((cx, cy - 18 * s), (cx - 9 * s, cy - 30 * s),
                           (cx - 13 * s, cy - 32 * s),
                           (cx - 15 * s, cy - 36 * s)), 2, C["wing_edge"])
    px.stroke(cubic_bezier((cx, cy - 18 * s), (cx + 9 * s, cy - 30 * s),
                           (cx + 13 * s, cy - 32 * s),
                           (cx + 15 * s, cy - 36 * s)), 2, C["wing_edge"])


def draw_air_butterflies(px):
    draw_butterfly(px, 872, 300, 42, C["wing_yellow"], tilt=16,
                   open_wings=1.0)
    draw_butterfly(px, 700, 150, 34, C["wing_white"], tilt=10,
                   open_wings=0.85)
    draw_butterfly(px, 130, 250, 40, C["wing_orange"], tilt=-20,
                   open_wings=1.0)
    draw_butterfly(px, 300, 430, 30, C["wing_pink"], tilt=-8,
                   open_wings=0.9)


# ------------------------------------------------------------------ puppy
def draw_puppy(px):
    # ---- body: a big golden mass, cropped at the bottom edge, with a
    # cream chest patch so head and body read as one puppy
    px.ellipse(512, 935, 305, 290, C["fur"])
    px.ellipse(512, 868, 180, 158, C["fur_cream"])
    # ---- front paws with toe lines
    for paw_x in (412, 612):
        px.ellipse(paw_x, 950, 66, 50, C["fur_dark"])
        px.ellipse(paw_x, 950, 60, 44, C["fur_pale"])
        for dx in (-20, 8):
            px.stroke([(paw_x + dx, 934), (paw_x + dx, 966)], 4,
                      C["fur_dark"], 0.7)

    # ---- floppy ears: long drooping shapes beside the head, darker
    # gold outside, lighter inside, one ear flopped a touch lower
    px.polygon([(352, 380), (398, 372), (392, 560), (330, 640),
                (288, 560), (300, 430)], C["fur_dark"])
    px.circle(330, 618, 24, C["fur_dark"])  # rounded ear tip
    px.polygon([(672, 380), (626, 372), (632, 560), (694, 640),
                (736, 560), (724, 430)], C["fur_dark"])
    px.circle(694, 618, 24, C["fur_dark"])  # rounded ear tip
    px.polygon([(356, 420), (384, 420), (378, 556), (336, 606),
                (310, 540)], C["ear_in"])
    px.polygon([(668, 420), (640, 420), (646, 556), (688, 606),
                (714, 540)], C["ear_in"])

    # ---- head, with a lighter face front and a tuft on top
    px.circle(512, 468, 198, C["fur"])
    px.ellipse(512, 496, 162, 146, C["fur_cream"])
    px.polygon([(468, 292), (488, 258), (504, 292)], C["fur"])
    px.polygon([(500, 288), (524, 252), (540, 290)], C["fur"])
    px.polygon([(530, 290), (554, 262), (564, 294)], C["fur"])

    # ---- happy closed eyes: squeezed-shut upward arcs
    for ex in (390, 566):
        px.stroke(cubic_bezier((ex, 442), (ex + 16, 408), (ex + 50, 408),
                               (ex + 66, 442)), 15, C["eye"])
    # ---- rosy cheeks
    px.circle(396, 560, 28, C["blush"], 0.5)
    px.circle(628, 560, 28, C["blush"], 0.5)

    # ---- muzzle, nose, open smiling mouth, tongue
    px.ellipse(512, 578, 128, 88, C["fur_pale"])
    px.ellipse(512, 516, 42, 28, C["nose"])
    px.circle(498, 506, 6, C["wing_white"], 0.85)  # nose glint
    px.ellipse(512, 604, 48, 36, C["mouth"])
    px.ellipse(512, 620, 30, 26, C["tongue"])
    px.stroke([(512, 600), (512, 634)], 4, C["tongue_dk"], 0.8)
    # smile creases sweeping up from the mouth corners
    px.stroke(cubic_bezier((464, 600), (448, 574), (442, 556), (436, 548)),
              6, C["eye"], 0.8)
    px.stroke(cubic_bezier((560, 600), (576, 574), (582, 556), (588, 548)),
              6, C["eye"], 0.8)
    # whisker dots on the muzzle
    for dx, dy in [(-82, -6), (-90, 14), (82, -6), (90, 14),
                   (-68, 24), (68, 24)]:
        px.circle(512 + dx, 578 + dy, 3, C["fur_dark"], 0.7)

    # ---- the surprise: an orange butterfly has landed on the nose,
    # wings half-folded, right between the puppy's eyes
    draw_butterfly(px, 512, 478, 56, C["wing_orange"], tilt=0,
                   open_wings=0.55)


# ------------------------------------------------------------------ PNG out
def png_chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def encode_png(px):
    raw = bytearray()
    for y in range(px.h):
        raw.append(0)  # filter type: none
        raw += px.buf[y * px.w * 3:(y + 1) * px.w * 3]
    body = b"\x89PNG\r\n\x1a\n"
    body += png_chunk(b"IHDR",
                      struct.pack(">IIBBBBB", px.w, px.h, 8, 2, 0, 0, 0))
    body += png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    body += png_chunk(b"IEND", b"")
    return body


def build_scene():
    rng = Random(RNG_SEED)
    px = Pixmap(W, H)
    draw_sky(px)
    draw_hills(px)
    draw_meadow(px)
    draw_grass(px, rng)
    draw_flowers(px, rng)
    draw_puppy(px)
    draw_air_butterflies(px)
    return px


def main():
    px = build_scene()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", ".")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    data = encode_png(px)
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
