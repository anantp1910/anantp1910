#!/usr/bin/env python3
"""
art.py draws the profile artwork into assets/ (light + dark versions of each):

    hero      jump smash on a badminton court, flip scoreboard (anant vs bugs)
    net       badminton-net divider
    footer    cricket, pickleball and volleyball pictograms

    python scripts/art.py           # needs: pip install fonttools brotli

Edit the TEXT block below to change words in the art.
"""
from __future__ import annotations

import base64
import html
import io
import math
from pathlib import Path

from fontTools import subset as ftsubset

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONTS = ROOT / "scripts" / "fonts"

TEXT = {
    "me": "anant",
    "them": "bugs",
    "score_from": 20,   # flips to score_from + 1 when the smash lands
    "their_score": 19,
    "code": "while (rally) { smash(); ship(); }",
    "footer": "good game. thanks for stopping by.",
    "footer_sub": "off the court: cricket, pickleball, volleyball",
}

# ───────────────────────── palette ─────────────────────────
# badminton-mat green, feather white, red cork tape, charcoal flip cards
THEMES = {
    "light": dict(
        ink="#17212d", dim="#5b6876", faint="#9aa5b1",
        court="#2c7a56", court_dark="#246649", line="#f4f6f2",
        floor="#e7dcc9", floor_line="#d8cab2",
        feather="#fdfcf8", feather_line="#17212d", cork="#d1433a", tape="#2a4fd0",
        card="#1d222b", card_edge="#2b313c", digit="#f7f4ec", hinge="#0b0d11",
        net="#17212d", net_alpha=0.30, glow=0.0, shadow=0.20,
        willow="#d8b47e", paddle="#2a4fd0", pball="#e6c92e", vball_a="#f1c230", vball_b="#2a4fd0",
    ),
    "dark": dict(
        ink="#eef0ea", dim="#93a0ad", faint="#5d6874",
        court="#1f5b43", court_dark="#194b37", line="#e9eee9",
        floor="#1b1a17", floor_line="#26241f",
        feather="#fbfaf6", feather_line="#fbfaf6", cork="#e0564c", tape="#5b7cf0",
        card="#20252e", card_edge="#353c48", digit="#f7f4ec", hinge="#0b0d11",
        net="#e2e6ea", net_alpha=0.26, glow=0.11, shadow=0.45,
        willow="#d8b47e", paddle="#5b7cf0", pball="#e6c92e", vball_a="#f1c230", vball_b="#5b7cf0",
    ),
}

# ───────────────────────── fonts ─────────────────────────
FONT_FILES = {
    "mono": ("JetBrains Mono", 400, "JetBrainsMono-Regular.woff2"),
    "bs8": ("Big Shoulders", 800, "BigShouldersDisplay-800.woff2"),
    "bs9": ("Big Shoulders", 900, "BigShouldersDisplay-900.woff2"),
}
_cache: dict = {}


def font_face(key: str, chars: str) -> str:
    family, weight, fname = FONT_FILES[key]
    ck = (key, chars)
    if ck not in _cache:
        opts = ftsubset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["*"]
        opts.hinting = False
        font = ftsubset.load_font(str(FONTS / fname), opts)
        sub = ftsubset.Subsetter(opts)
        sub.populate(text=chars + " ")
        sub.subset(font)
        buf = io.BytesIO()
        ftsubset.save_font(font, buf, opts)
        _cache[ck] = base64.b64encode(buf.getvalue()).decode()
    alias = {"mono": "M", "bs8": "B8", "bs9": "B9"}[key]
    return f"@font-face{{font-family:{alias};font-weight:{weight};src:url(data:font/woff2;base64,{_cache[ck]}) format('woff2')}}"


def esc(s) -> str:
    return html.escape(str(s), quote=False)


class Svg:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.defs, self.body, self.css = [], [], []
        self.chars = {"mono": set(), "bs8": set(), "bs9": set()}

    def add(self, s):
        self.body.append(s)

    def text(self, x, y, s, font="bs8", size=20, fill="#000", anchor="start", extra=""):
        self.chars[font].update(s)
        fam = {"mono": "M,ui-monospace,Menlo,Consolas,monospace", "bs8": "B8,Impact,sans-serif", "bs9": "B9,Impact,sans-serif"}[font]
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}" fill="{fill}" '
                 f'text-anchor="{anchor}"{extra}>{esc(s)}</text>')

    def render(self):
        faces = "".join(font_face(k, "".join(sorted(v))) for k, v in self.chars.items() if v)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                f'role="img" aria-label="{html.escape(self.title)}"><title>{esc(self.title)}</title>'
                f'<style>{faces}{"".join(self.css)}</style><defs>{"".join(self.defs)}</defs>{"".join(self.body)}</svg>')


# ───────────────────────── geometry ─────────────────────────

def homography(src, dst):
    """3x3 matrix mapping 4 src points to 4 dst points (plain Gaussian elimination)."""
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    n = 8
    M = [row[:] + [bb] for row, bb in zip(A, b)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [a - f * bv for a, bv in zip(M[r], M[c])]
    h = [M[i][n] / M[i][i] for i in range(n)] + [1.0]
    return [h[0:3], h[3:6], h[6:9]]


class Court:
    """Badminton court (metres: X across -3.05..3.05, Z from near baseline 0..13.4) in perspective."""
    W2, L = 3.05, 13.4

    def __init__(self, near_l, near_r, far_l, far_r):
        self.H = homography([(-self.W2, 0), (self.W2, 0), (-self.W2, self.L), (self.W2, self.L)],
                            [near_l, near_r, far_l, far_r])

    def p(self, X, Z, Y=0.0):
        h = self.H
        w = h[2][0] * X + h[2][1] * Z + h[2][2]
        x = (h[0][0] * X + h[0][1] * Z + h[0][2]) / w
        y = (h[1][0] * X + h[1][1] * Z + h[1][2]) / w
        return (x, y - Y * self.scale(Z)) if Y else (x, y)

    def scale(self, Z):
        """pixels per metre at depth Z"""
        a = self.p(-self.W2, Z)
        b = self.p(self.W2, Z)
        return (b[0] - a[0]) / (2 * self.W2)

    def quad(self, x0, z0, x1, z1):
        pts = [self.p(x0, z0), self.p(x1, z0), self.p(x1, z1), self.p(x0, z1)]
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def pts(seq):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in seq)


# ───────────────────────── pictograms ─────────────────────────
# Poses are joint angles (degrees: 0 = facing direction, 90 = up, -90 = down) on fixed body proportions,
# drawn as tapered limbs with small knockout gaps, in the spirit of Olympic sports pictograms.

SEG = dict(torso=52, neck=21, upper=30, fore=33, thigh=46, shin=47)
WID = dict(torso=(19, 23), upper=(11, 9.5), fore=(9.5, 8), thigh=(15.5, 12.5), shin=(12.5, 9.5), head=12)


def pose(a: dict, air: float = 0.0) -> dict:
    """Forward kinematics -> joints (y up). The lowest foot sits `air` units above the floor."""
    def d(deg, L):
        r = math.radians(deg)
        return (L * math.cos(r), L * math.sin(r))

    def add(p, q):
        return (p[0] + q[0], p[1] + q[1])

    J = {"hip": (0.0, 0.0)}
    J["neck"] = add(J["hip"], d(a["torso"], SEG["torso"]))
    J["head"] = add(J["neck"], d(a.get("head", a["torso"]), SEG["neck"]))
    sh = add(J["neck"], d(a["torso"] + 180, 5))
    for side in ("f", "b"):
        J[f"sh_{side}"] = sh
        J[f"elbow_{side}"] = add(sh, d(a[f"upper_{side}"], SEG["upper"]))
        J[f"hand_{side}"] = add(J[f"elbow_{side}"], d(a[f"fore_{side}"], SEG["fore"]))
        J[f"knee_{side}"] = add(J["hip"], d(a[f"thigh_{side}"], SEG["thigh"]))
        J[f"foot_{side}"] = add(J[f"knee_{side}"], d(a[f"shin_{side}"], SEG["shin"]))
    low = min(J["foot_f"][1], J["foot_b"][1]) - 5
    return {k: (x, y - low + air) for k, (x, y) in J.items()}


def capsule(a, b, wa, wb):
    """Tapered capsule from a (width wa) to b (width wb), as one path."""
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / L, dx / L
    ra, rb = wa / 2, wb / 2
    p1 = (x1 + nx * ra, y1 + ny * ra); p2 = (x2 + nx * rb, y2 + ny * rb)
    p3 = (x2 - nx * rb, y2 - ny * rb); p4 = (x1 - nx * ra, y1 - ny * ra)
    return (f"M{p1[0]:.1f},{p1[1]:.1f} L{p2[0]:.1f},{p2[1]:.1f} A{rb:.1f},{rb:.1f} 0 1 0 {p3[0]:.1f},{p3[1]:.1f} "
            f"L{p4[0]:.1f},{p4[1]:.1f} A{ra:.1f},{ra:.1f} 0 1 0 {p1[0]:.1f},{p1[1]:.1f} Z")


_fig_id = [0]


def figure(J: dict, ox: float, oy: float, s: float, color: str, flip: bool = False, gap: float = 3.2) -> str:
    """Draw a posed figure with its feet-floor at (ox, oy), scale s px/unit. Facing right unless flip."""
    def P(name):
        x, y = J[name]
        return (ox + (-x if flip else x) * s, oy - y * s)

    def limb(a, b, key):
        wa, wb = WID[key]
        return capsule(P(a), P(b), wa * s, wb * s)

    back = [limb("hip", "knee_b", "thigh"), limb("knee_b", "foot_b", "shin"),
            limb("sh_b", "elbow_b", "upper"), limb("elbow_b", "hand_b", "fore")]
    torso = [limb("hip", "neck", "torso")]
    front = [limb("hip", "knee_f", "thigh"), limb("knee_f", "foot_f", "shin"),
             limb("sh_f", "elbow_f", "upper"), limb("elbow_f", "hand_f", "fore")]
    hx, hy = P("head")
    head = f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{WID["head"] * s:.1f}"/>'
    _fig_id[0] += 1
    mid = f"k{_fig_id[0]}"
    g = gap * s
    knock = "".join(f'<path d="{d}" fill="#000" stroke="#000" stroke-width="{2 * g:.1f}" stroke-linejoin="round"/>' for d in front)
    knock_t = "".join(f'<path d="{d}" fill="#000" stroke="#000" stroke-width="{2 * g:.1f}"/>' for d in torso)
    return (f'<mask id="{mid}a" maskUnits="userSpaceOnUse" x="-5000" y="-5000" width="10000" height="10000">'
            f'<rect x="-5000" y="-5000" width="10000" height="10000" fill="#fff"/>{knock_t}{knock}</mask>'
            f'<mask id="{mid}b" maskUnits="userSpaceOnUse" x="-5000" y="-5000" width="10000" height="10000">'
            f'<rect x="-5000" y="-5000" width="10000" height="10000" fill="#fff"/>{knock}</mask>'
            f'<g fill="{color}"><g mask="url(#{mid}a)">{"".join(f"<path d={chr(34)}{d}{chr(34)}/>" for d in back)}</g>'
            f'<g mask="url(#{mid}b)">{"".join(f"<path d={chr(34)}{d}{chr(34)}/>" for d in torso)}</g>'
            f'<g mask="url(#{mid}b)">{head}</g>{"".join(f"<path d={chr(34)}{d}{chr(34)}/>" for d in front)}</g>')


def to_screen(J, name, ox, oy, s, flip=False):
    x, y = J[name]
    return (ox + (-x if flip else x) * s, oy - y * s)


A_SMASH = dict(torso=102, head=106, upper_f=66, fore_f=76, upper_b=-28, fore_b=-62,
               thigh_f=-36, shin_f=-114, thigh_b=-100, shin_b=-128)
A_BATTER = dict(torso=66, head=60, upper_f=-62, fore_f=-48, upper_b=-70, fore_b=-52,
                thigh_f=-28, shin_f=-88, thigh_b=-128, shin_b=-112)
A_PICKLE = dict(torso=74, head=74, upper_f=-18, fore_f=12, upper_b=-108, fore_b=-62,
                thigh_f=-52, shin_f=-98, thigh_b=-116, shin_b=-82)
A_SPIKE = dict(torso=104, head=98, upper_f=96, fore_f=74, upper_b=24, fore_b=46,
               thigh_f=-66, shin_f=-146, thigh_b=-96, shin_b=-160)

SMASH = pose(A_SMASH, air=30)
BATTER = pose(A_BATTER)
PICKLE = pose(A_PICKLE)
SPIKE = pose(A_SPIKE, air=34)


def shuttle(t: dict, size: float = 1.0) -> str:
    """Shuttlecock pointing +x (cork leads), drawn around the origin."""
    s = size
    fl = t["feather_line"]
    skirt = f'M{-2 * s:.1f},{-5 * s:.1f} L{-26 * s:.1f},{-13 * s:.1f} Q{-29 * s:.1f},0 {-26 * s:.1f},{13 * s:.1f} L{-2 * s:.1f},{5 * s:.1f} Z'
    ribs = "".join(f'<path d="M{-3 * s:.1f},{k * 1.1 * s:.1f} L{-26 * s:.1f},{k * 3 * s:.1f}" stroke="{fl}" stroke-opacity=".35" stroke-width="{.8 * s:.1f}"/>'
                   for k in (-3, -1, 1, 3))
    return (f'<path d="{skirt}" fill="{t["feather"]}" stroke="{fl}" stroke-opacity=".55" stroke-width="{1 * s:.1f}" stroke-linejoin="round"/>{ribs}'
            f'<rect x="{-4 * s:.1f}" y="{-5.2 * s:.1f}" width="{3.2 * s:.1f}" height="{10.4 * s:.1f}" fill="{t["tape"]}"/>'
            f'<path d="M{-1 * s:.1f},{-5.2 * s:.1f} A{5.4 * s:.1f},{5.2 * s:.1f} 0 0 1 {-1 * s:.1f},{5.2 * s:.1f} Z" fill="{t["cork"]}"/>')


# ───────────────────────── hero ─────────────────────────

CAMERA = ((1.6, 4.4, -12.0), (7.4, 0.7, 1.0), 980, 540, 262)
FADE_TOP = 200
PLAYER_AT = (3.1, -0.8)
PLAYER_SCALE = 1.32


class Cam:
    """Pinhole camera. World: x along the court (0..13.4 m), y up, z across (-3.05 near .. 3.05 far)."""

    def __init__(self, pos, target, f, cx, cy):
        self.c, self.f, self.cx, self.cy = pos, f, cx, cy
        fw = [t - p for t, p in zip(target, pos)]
        n = math.sqrt(sum(v * v for v in fw)); self.fw = [v / n for v in fw]
        up = (0, 1, 0)
        r = [up[1] * self.fw[2] - up[2] * self.fw[1], up[2] * self.fw[0] - up[0] * self.fw[2], up[0] * self.fw[1] - up[1] * self.fw[0]]
        n = math.sqrt(sum(v * v for v in r)); self.r = [v / n for v in r]
        f_, r_ = self.fw, self.r
        self.u = [f_[1] * r_[2] - f_[2] * r_[1], f_[2] * r_[0] - f_[0] * r_[2], f_[0] * r_[1] - f_[1] * r_[0]]

    def p(self, x, y, z):
        d = (x - self.c[0], y - self.c[1], z - self.c[2])
        xc = sum(a * b for a, b in zip(d, self.r)); yc = sum(a * b for a, b in zip(d, self.u)); zc = sum(a * b for a, b in zip(d, self.fw))
        return (self.cx + self.f * xc / zc, self.cy - self.f * yc / zc)

    def k(self, x, y, z):
        """pixels per metre at a point"""
        d = (x - self.c[0], y - self.c[1], z - self.c[2])
        return self.f / sum(a * b for a, b in zip(d, self.fw))

    def floor_rect(self, x0, x1, z0, z1, y=0.0):
        return pts([self.p(x0, y, z0), self.p(x1, y, z0), self.p(x1, y, z1), self.p(x0, y, z1)])


def render_hero(t: dict, mode: str) -> str:
    W, H = 1200, 460
    svg = Svg(W, H, f"Badminton jump smash. The shuttle clears the net, lands in, and the scoreboard flips to "
                    f"{TEXT['me']} {TEXT['score_from'] + 1}, {TEXT['them']} {TEXT['their_score']}. {TEXT['code']}")
    cam = Cam(*CAMERA)

    svg.defs.append('<linearGradient id="fv" x1="0" y1="0" x2="0" y2="1">'
                    '<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".25" stop-color="#fff"/>'
                    '<stop offset=".78" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
                    '<linearGradient id="fh" x1="0" y1="0" x2="1" y2="0">'
                    '<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".14" stop-color="#fff"/>'
                    '<stop offset=".86" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
                    f'<mask id="mv" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><rect y="{FADE_TOP}" width="{W}" height="{H - FADE_TOP}" fill="url(#fv)"/></mask>'
                    f'<mask id="mh" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="url(#fh)"/></mask>')

    # hall floor, court mat, lines
    svg.add('<g mask="url(#mh)"><g mask="url(#mv)">')
    svg.add(f'<polygon points="{cam.floor_rect(-9, 22, -6, 14)}" fill="{t["floor"]}"/>')
    for zb in [z * 0.9 for z in range(-6, 16)]:
        a, b = cam.p(-9, 0, zb), cam.p(22, 0, zb)
        svg.add(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{t["floor_line"]}" stroke-width="1"/>')
    svg.add(f'<polygon points="{cam.floor_rect(-0.7, 14.1, -3.75, 3.75)}" fill="{t["court"]}"/>')
    w = 0.05
    rects = [(0, w, -3.05, 3.05), (13.4 - w, 13.4, -3.05, 3.05), (0.76, 0.76 + w, -3.05, 3.05), (12.64 - w, 12.64, -3.05, 3.05),
             (4.72, 4.72 + w, -3.05, 3.05), (8.68 - w, 8.68, -3.05, 3.05),
             (0, 13.4, -3.05, -3.05 + w), (0, 13.4, 3.05 - w, 3.05), (0, 13.4, -2.59, -2.59 + w), (0, 13.4, 2.59 - w, 2.59),
             (0, 4.72, -w / 2, w / 2), (8.68, 13.4, -w / 2, w / 2)]
    for x0, x1, z0, z1 in rects:
        svg.add(f'<polygon points="{cam.floor_rect(x0, x1, z0, z1)}" fill="{t["line"]}" fill-opacity=".95"/>')
    svg.add("</g></g>")

    # timings for the one animated moment
    t0, tf = 0.45, 0.6
    t_land = t0 + tf

    # landing spot + call
    land = (11.55, 1.35)
    ring = [cam.p(land[0] + 0.36 * math.cos(a / 24 * 2 * math.pi), 0, land[1] + 0.36 * math.sin(a / 24 * 2 * math.pi)) for a in range(24)]
    dot_ = [cam.p(land[0] + 0.13 * math.cos(a / 16 * 2 * math.pi), 0, land[1] + 0.13 * math.sin(a / 16 * 2 * math.pi)) for a in range(16)]
    lx, ly = cam.p(land[0], 0, land[1])
    svg.add(f'<g class="pop" style="transform-origin:{lx:.1f}px {ly:.1f}px;animation:pop .5s cubic-bezier(.2,1.7,.4,1) {t_land:.2f}s both">'
            f'<polygon points="{pts(ring)}" fill="none" stroke="{t["cork"]}" stroke-width="2.2"/>'
            f'<polygon points="{pts(dot_)}" fill="{t["cork"]}"/></g>')
    svg.add(f'<g class="pop" style="transform-origin:{lx:.1f}px {ly:.1f}px;animation:pop .5s cubic-bezier(.2,1.7,.4,1) {t_land + .12:.2f}s both">')
    svg.text(lx + 22, ly - 8, "in", font="bs9", size=28, fill=t["line"])
    svg.add("</g>")

    # the player (left court), drawn before the net only if nearer... the player is on the near-left, net is behind
    px3, pz3 = PLAYER_AT
    fx, fy = cam.p(px3, 0, pz3)
    ps = cam.k(px3, 0, pz3) / 100 * PLAYER_SCALE
    racket_parts, head_c = racket(SMASH, fx, fy, ps, t)

    # net (posts, mesh, tape)
    nx = 6.7
    tl, tr_ = cam.p(nx, 1.55, -3.05), cam.p(nx, 1.55, 3.05)
    bl, br = cam.p(nx, 0.79, -3.05), cam.p(nx, 0.79, 3.05)
    svg.defs.append(f'<pattern id="mesh" width="6" height="6" patternUnits="userSpaceOnUse">'
                    f'<path d="M0,0 H6 M0,0 V6" stroke="{t["net"]}" stroke-width=".8" fill="none"/></pattern>')
    svg.add(f'<polygon points="{pts([tl, tr_, br, bl])}" fill="url(#mesh)" opacity="{t["net_alpha"] + .3:.2f}"/>')
    svg.add(f'<line x1="{bl[0]:.1f}" y1="{bl[1]:.1f}" x2="{br[0]:.1f}" y2="{br[1]:.1f}" stroke="{t["net"]}" stroke-opacity=".55" stroke-width="1.3"/>')
    tape_b = (cam.p(nx, 1.50, -3.05), cam.p(nx, 1.50, 3.05))
    svg.add(f'<polygon points="{pts([tl, tr_, tape_b[1], tape_b[0]])}" fill="{t["line"]}"' +
            (f' stroke="{t["ink"]}" stroke-opacity=".25" stroke-width=".8"' if mode == "light" else "") + "/>")
    for z in (-3.05, 3.05):
        a, b = cam.p(nx, 0, z), cam.p(nx, 1.58, z)
        svg.add(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{t["ink"]}" stroke-opacity=".85" stroke-width="{3.6 if z < 0 else 2.6}" stroke-linecap="round"/>')

    # trajectory: racket head -> just over the tape -> landing spot
    start3 = (px3 + 0.45, 2.95, pz3)
    path = []
    N = 44
    for i in range(N + 1):
        u = i / N
        x = start3[0] + (land[0] - start3[0]) * u
        z = start3[2] + (land[1] - start3[2]) * u
        y = start3[1] * (1 - u) ** 1.08 + 0.2 * math.sin(math.pi * u)
        path.append(cam.p(x, y, z))
    off = (head_c[0] - path[0][0], head_c[1] - path[0][1])
    path = [(x + off[0] * (1 - i / N) ** 2, y + off[1] * (1 - i / N) ** 2) for i, (x, y) in enumerate(path)]
    for i, (x, y) in enumerate(path[1:-1], start=1):
        if i % 2:
            continue
        svg.add(f'<circle class="tr" cx="{x:.1f}" cy="{y:.1f}" r="{1.3 + 1.5 * (1 - i / N):.1f}" fill="{t["ink"]}" '
                f'fill-opacity=".42" style="animation-delay:{t0 + tf * i / N:.2f}s"/>')

    # player last (nearest the camera)
    svg.add(f'<ellipse cx="{fx:.1f}" cy="{fy:.1f}" rx="{44 * ps:.1f}" ry="{8 * ps:.1f}" fill="#000" fill-opacity="{t["shadow"]}"/>')
    svg.add(racket_parts)
    svg.add(figure(SMASH, fx, fy, ps, t["ink"]))

    # shuttle flight
    kf = []
    for i, (x, y) in enumerate(path):
        j, k = min(i + 1, N), max(i - 1, 0)
        a = math.degrees(math.atan2(path[j][1] - path[k][1], path[j][0] - path[k][0]))
        sc = 1.25 - 0.55 * i / N
        kf.append(f"{100 * i / N:.1f}%{{transform:translate({x:.1f}px,{y:.1f}px) rotate({a:.1f}deg) scale({sc:.2f})}}")
    end_t = kf[-1].split("transform:", 1)[1].rstrip("}")
    svg.css.append("@keyframes fly{" + "".join(kf) + "}")
    svg.add(f'<g class="fly" style="animation:fly {tf:.2f}s linear {t0:.2f}s both">{shuttle(t, 1.0)}</g>')

    # flip scoreboard (top right)
    me, them = TEXT["score_from"], TEXT["their_score"]
    cw, ch, gap = 46, 66, 4
    bx, by = 900, 92
    unit = cw * 2 + gap
    for col, (name, score) in enumerate(((TEXT["me"], me), (TEXT["them"], them))):
        ux = bx + col * (unit + 26)
        svg.text(ux + unit / 2, by - 14, name, font="bs8", size=27, fill=t["ink"], anchor="middle")
        for d in range(2):
            x = ux + d * (cw + gap)
            old = f"{score:02d}"[d]
            flips = col == 0 and old != f"{me + 1:02d}"[d]
            draw_card(svg, t, x, by, cw, ch, old, f"{me + 1:02d}"[d] if flips else None, t_land + .3)
    sw = unit * 2 + 26
    svg.add(f'<rect x="{bx - 8}" y="{by + ch + 9}" width="{sw + 16}" height="5" rx="2.5" fill="{t["ink"]}" fill-opacity=".85"/>')
    svg.text(bx + sw / 2 - 6, by + ch + 48, TEXT["code"], font="mono", size=16.5, fill=t["dim"], anchor="middle")

    svg.css.append(
        "@keyframes pop{from{transform:scale(.3);opacity:0}to{transform:scale(1);opacity:1}}"
        ".tr{opacity:0;animation:on .01s linear forwards}@keyframes on{to{opacity:1}}"
        "@keyframes fu{to{transform:scaleY(0)}}@keyframes fl{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
        f"@media (prefers-reduced-motion:reduce){{.fly{{animation:none!important;transform:{end_t}}}"
        ".tr,.pop{animation:none!important;opacity:1}.fu{display:none}.fl{animation:none!important;transform:none}}"
    )
    return svg.render()


def racket(J, ox, oy, s, t):
    """Racket held in the front hand, continuing the forearm. Returns (svg, head centre)."""
    e, h = to_screen(J, "elbow_f", ox, oy, s), to_screen(J, "hand_f", ox, oy, s)
    ang = math.atan2(h[1] - e[1], h[0] - e[0]) - math.radians(8)
    sh_end = (h[0] + math.cos(ang) * 36 * s, h[1] + math.sin(ang) * 36 * s)
    c = (h[0] + math.cos(ang) * 52 * s, h[1] + math.sin(ang) * 52 * s)
    rot = math.degrees(ang) + 90
    rx, ry = 10 * s, 14 * s
    cid = f"str{int(c[0])}"
    strings = "".join(f'<line x1="{c[0] + k * 3.3 * s:.1f}" y1="{c[1] - 20 * s:.1f}" x2="{c[0] + k * 3.3 * s:.1f}" y2="{c[1] + 20 * s:.1f}"/>' for k in range(-3, 4))
    strings += "".join(f'<line x1="{c[0] - 20 * s:.1f}" y1="{c[1] + k * 3.3 * s:.1f}" x2="{c[0] + 20 * s:.1f}" y2="{c[1] + k * 3.3 * s:.1f}"/>' for k in range(-4, 5))
    out = (f'<clipPath id="{cid}"><ellipse cx="{c[0]:.1f}" cy="{c[1]:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" transform="rotate({rot:.1f} {c[0]:.1f} {c[1]:.1f})"/></clipPath>'
           f'<line x1="{h[0]:.1f}" y1="{h[1]:.1f}" x2="{sh_end[0]:.1f}" y2="{sh_end[1]:.1f}" stroke="{t["ink"]}" stroke-width="{3 * s:.1f}" stroke-linecap="round"/>'
           f'<g clip-path="url(#{cid})" stroke="{t["ink"]}" stroke-opacity=".38" stroke-width=".7"><g transform="rotate({rot:.1f} {c[0]:.1f} {c[1]:.1f})">{strings}</g></g>'
           f'<ellipse cx="{c[0]:.1f}" cy="{c[1]:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" transform="rotate({rot:.1f} {c[0]:.1f} {c[1]:.1f})" fill="none" stroke="{t["ink"]}" stroke-width="{2.8 * s:.1f}"/>')
    return out, c


def draw_card(svg: Svg, t: dict, x, y, w, h, old: str, new: str | None, t0: float):
    """One flip-card digit. If `new` is given, it flips old -> new at t0."""
    hinge = y + h / 2
    cid = f"c{int(x)}"
    svg.defs.append(f'<clipPath id="{cid}u"><rect x="{x}" y="{y}" width="{w}" height="{h / 2 - .6:.1f}"/></clipPath>'
                    f'<clipPath id="{cid}l"><rect x="{x}" y="{hinge + .6:.1f}" width="{w}" height="{h / 2}"/></clipPath>')

    def half(ch_, which, cls="", style=""):
        g = f'<g clip-path="url(#{cid}{which})"{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}{f" style={chr(34)}{style}{chr(34)}" if style else ""}>'
        g += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{t["card"]}" stroke="{t["card_edge"]}"/>'
        inner = Svg(0, 0, "")
        inner.chars = svg.chars
        inner.body = []
        inner.text(x + w / 2, y + h * 0.83, ch_, font="bs9", size=h * 0.92, fill=t["digit"], anchor="middle")
        g += "".join(inner.body) + "</g>"
        return g

    origin = f"transform-origin:{x + w / 2:.1f}px {hinge:.1f}px"
    if new is None:
        svg.add(half(old, "u") + half(old, "l"))
    else:
        svg.add(half(new, "u"))                                   # revealed when the old top folds away
        svg.add(half(old, "l"))                                   # covered when the new bottom drops
        svg.add(half(old, "u", "fu", f"{origin};animation:fu .14s ease-in {t0:.2f}s forwards"))
        svg.add(half(new, "l", "fl", f"{origin};transform:scaleY(0);animation:fl .16s ease-out {t0 + .14:.2f}s forwards"))
    svg.add(f'<line x1="{x}" y1="{hinge:.1f}" x2="{x + w}" y2="{hinge:.1f}" stroke="{t["hinge"]}" stroke-width="1.6"/>')


# ───────────────────────── net divider ─────────────────────────

def render_net(t: dict, mode: str) -> str:
    W, H = 1200, 52
    svg = Svg(W, H, "")
    x0, x1, top, bot = 28, W - 28, 16, 36
    svg.defs.append(f'<pattern id="m" width="7" height="7" patternUnits="userSpaceOnUse">'
                    f'<path d="M0,0 H7 M0,0 V7" stroke="{t["net"]}" stroke-width=".9" fill="none"/></pattern>')
    svg.add(f'<rect x="{x0}" y="{top}" width="{x1 - x0}" height="{bot - top}" fill="url(#m)" opacity="{t["net_alpha"] + .05:.2f}"/>')
    svg.add(f'<line x1="{x0}" y1="{bot}" x2="{x1}" y2="{bot}" stroke="{t["net"]}" stroke-opacity=".45" stroke-width="1.2"/>')
    svg.add(f'<rect x="{x0}" y="{top - 3}" width="{x1 - x0}" height="5" fill="{t["line"]}"' +
            (f' stroke="{t["ink"]}" stroke-opacity=".28" stroke-width=".8"' if mode == "light" else "") + "/>")
    for x in (x0, x1):
        svg.add(f'<line x1="{x}" y1="{top - 6}" x2="{x}" y2="{H - 4}" stroke="{t["ink"]}" stroke-opacity=".8" stroke-width="4" stroke-linecap="round"/>')
    # a shuttle that clipped the tape
    svg.add(f'<g transform="translate(828 {top - 8}) rotate(-8)">{shuttle(t, .6)}</g>')
    return svg.render()


# ───────────────────────── footer ─────────────────────────

def render_footer(t: dict, mode: str) -> str:
    W, H = 1200, 350
    svg = Svg(W, H, f"Pictograms of a cricket batter, a pickleball player and a volleyball spike. {TEXT['footer']}")
    floor = 238
    s = 0.92
    # floor line
    svg.add(f'<line x1="150" y1="{floor}" x2="{W - 150}" y2="{floor}" stroke="{t["ink"]}" stroke-opacity=".18" stroke-width="1.5"/>')

    # cricket batter
    cx = 320
    svg.add(f'<ellipse cx="{cx + 6:.1f}" cy="{floor}" rx="60" ry="6" fill="#000" fill-opacity="{t["shadow"] * .7}"/>')
    hb = to_screen(BATTER, "hand_b", cx, floor, s)
    bat_dir = math.radians(64)
    handle_end = (hb[0] + math.cos(bat_dir) * 20 * s, hb[1] + math.sin(bat_dir) * 20 * s)
    blade_end = (hb[0] + math.cos(bat_dir) * 82 * s, hb[1] + math.sin(bat_dir) * 82 * s)
    svg.add(f'<line x1="{hb[0]:.1f}" y1="{hb[1]:.1f}" x2="{handle_end[0]:.1f}" y2="{handle_end[1]:.1f}" stroke="{t["ink"]}" stroke-width="{4.5 * s:.1f}" stroke-linecap="round"/>')
    svg.add(f'<line x1="{handle_end[0]:.1f}" y1="{handle_end[1]:.1f}" x2="{blade_end[0]:.1f}" y2="{blade_end[1]:.1f}" stroke="{t["willow"]}" stroke-width="{12 * s:.1f}" stroke-linecap="round"/>')
    svg.add(figure(BATTER, cx, floor, s, t["ink"]))
    head = to_screen(BATTER, "head", cx, floor, s)
    svg.add(f'<path d="M{head[0] + 6 * s:.1f},{head[1] - 2 * s:.1f} l{14 * s:.1f},{3 * s:.1f}" stroke="{t["ink"]}" stroke-width="{4 * s:.1f}" stroke-linecap="round"/>')
    ball = (blade_end[0] + 40, floor - 34)
    svg.add(f'<circle cx="{ball[0]:.1f}" cy="{ball[1]:.1f}" r="7" fill="{t["cork"]}"/>'
            f'<path d="M{ball[0] - 2.5:.1f},{ball[1] - 6.5:.1f} q4,6.5 0,13" stroke="#fff" stroke-opacity=".8" stroke-width="1" fill="none"/>')
    for k in range(3):
        svg.add(f'<line x1="{ball[0] - 16 - k * 13:.1f}" y1="{ball[1] + 2 + k * 2.5:.1f}" x2="{ball[0] - 23 - k * 13:.1f}" y2="{ball[1] + 3 + k * 2.6:.1f}" stroke="{t["ink"]}" stroke-opacity="{.4 - k * .1:.2f}" stroke-width="2" stroke-linecap="round"/>')

    # pickleball
    cx = 600
    svg.add(f'<ellipse cx="{cx + 4:.1f}" cy="{floor}" rx="50" ry="6" fill="#000" fill-opacity="{t["shadow"] * .7}"/>')
    hf = to_screen(PICKLE, "hand_f", cx, floor, s)
    pc = (hf[0] + 20 * s, hf[1] - 4 * s)
    svg.add(f'<line x1="{hf[0]:.1f}" y1="{hf[1]:.1f}" x2="{pc[0]:.1f}" y2="{pc[1]:.1f}" stroke="{t["ink"]}" stroke-width="{5 * s:.1f}" stroke-linecap="round"/>')
    svg.add(f'<rect x="{pc[0] - 2:.1f}" y="{pc[1] - 17 * s:.1f}" width="{22 * s:.1f}" height="{28 * s:.1f}" rx="{8 * s:.1f}" fill="{t["paddle"]}" transform="rotate(14 {pc[0]:.1f} {pc[1]:.1f})"/>')
    svg.add(figure(PICKLE, cx, floor, s, t["ink"]))
    pb = (pc[0] + 52, pc[1] - 18)
    svg.add(f'<circle cx="{pb[0]:.1f}" cy="{pb[1]:.1f}" r="7.5" fill="{t["pball"]}"/>')
    for dx, dy in ((-3, -2.5), (2.5, -3), (3, 2), (-2, 3), (0, 0)):
        svg.add(f'<circle cx="{pb[0] + dx:.1f}" cy="{pb[1] + dy:.1f}" r="1.05" fill="#000" fill-opacity=".28"/>')
    svg.add(f'<path d="M{pc[0] + 18:.1f},{pc[1] - 12:.1f} Q{pc[0] + 34:.1f},{pc[1] - 34:.1f} {pb[0] - 9:.1f},{pb[1] - 2:.1f}" stroke="{t["ink"]}" stroke-opacity=".3" stroke-width="1.6" stroke-dasharray="2 5" stroke-linecap="round" fill="none"/>')

    # volleyball spike (facing left, toward the middle)
    cx = 880
    svg.add(f'<ellipse cx="{cx:.1f}" cy="{floor}" rx="40" ry="5" fill="#000" fill-opacity="{t["shadow"] * .45}"/>')
    svg.add(figure(SPIKE, cx, floor, s, t["ink"], flip=True))
    hand = to_screen(SPIKE, "hand_f", cx, floor, s, flip=True)
    vb = (hand[0] - 13, hand[1] - 9)
    r = 13
    svg.defs.append(f'<clipPath id="vb"><circle cx="{vb[0]:.1f}" cy="{vb[1]:.1f}" r="{r}"/></clipPath>')
    svg.add(f'<circle cx="{vb[0]:.1f}" cy="{vb[1]:.1f}" r="{r}" fill="{t["vball_a"]}"/>'
            f'<g clip-path="url(#vb)" fill="none" stroke-width="5">'
            f'<path d="M{vb[0] - r:.1f},{vb[1] + 3:.1f} Q{vb[0]:.1f},{vb[1] - 9:.1f} {vb[0] + r:.1f},{vb[1] + 1:.1f}" stroke="{t["vball_b"]}"/>'
            f'<path d="M{vb[0] - 3:.1f},{vb[1] - r:.1f} Q{vb[0] + 9:.1f},{vb[1]:.1f} {vb[0] - 1:.1f},{vb[1] + r:.1f}" stroke="{t["vball_b"]}" stroke-opacity=".55"/></g>'
            f'<circle cx="{vb[0]:.1f}" cy="{vb[1]:.1f}" r="{r}" fill="none" stroke="{t["ink"]}" stroke-opacity=".35"/>')

    svg.text(W / 2, floor + 60, TEXT["footer"], font="bs8", size=38, fill=t["ink"], anchor="middle")
    svg.text(W / 2, floor + 92, TEXT["footer_sub"], font="mono", size=16.5, fill=t["dim"], anchor="middle")
    return svg.render()


def main():
    ASSETS.mkdir(exist_ok=True)
    for name, fn in (("hero", render_hero), ("net", render_net), ("footer", render_footer)):
        for mode, theme in THEMES.items():
            out = ASSETS / f"{name}-{mode}.svg"
            out.write_text(fn(theme, mode), encoding="utf-8")
            print(f"{out.relative_to(ROOT)}  {out.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
