#!/usr/bin/env python3
"""Build the SVG artwork for the profile README (assets/*.svg).

Text is drawn from font outlines that are embedded once per file and reused
with <use>, so the art looks the same on every OS and needs no web fonts.
GitHub serves README images from a sandbox that would block them anyway.

  Sitka (ships with Windows) sets the name, the numbers and the prose.
  Cascadia Code (SIL OFL 1.1) sets labels, data and code.

    pip install fonttools
    python scripts/build_assets.py              # every card
    python scripts/build_assets.py upstream     # one card

The upstream card reads merged pull requests from the GitHub search API, using
GITHUB_TOKEN when it is set and `gh auth token` otherwise. Set FONT_DIR when
the fonts are not in C:/Windows/Fonts. The portrait comes from
scripts/portrait.txt (see make_portrait.py).

.github/workflows/readme-sync.yml rebuilds the upstream card every day on a
runner that has neither font. A build from the font files also saves every
glyph that card can need to scripts/glyphs.json, and a machine without the
fonts sets text from that file instead (standard library only).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
FONT_DIR = Path(os.environ.get("FONT_DIR", "C:/Windows/Fonts"))
GLYPHS = Path(__file__).resolve().parent / "glyphs.json"
PORTRAIT = Path(__file__).resolve().parent / "portrait.txt"
USER = "roydonsequeira"
README = ROOT / "README.md"
SEARCH = ("https://github.com/search?q=is%3Apr+is%3Amerged+author%3Aroydonsequeira"
          "+-user%3Aroydonsequeira&type=pullrequests")

# Face keys used by Svg.text(). Sitka's optical sizes: 27.5 is Banner, 11 is Text.
FACES = {
    "r": ("CascadiaCode.ttf", {"wght": 400}),
    "m": ("CascadiaCode.ttf", {"wght": 600}),
    "b": ("CascadiaCode.ttf", {"wght": 700}),
    "D": ("SitkaVF.ttf", {"opsz": 27.5, "wght": 400}),
    "Di": ("SitkaVF-Italic.ttf", {"opsz": 27.5, "wght": 400}),
    "T": ("SitkaVF.ttf", {"opsz": 11, "wght": 400}),
}
# What the daily rebuild of the upstream card may set beyond today's text:
# repository names in Cascadia, and new numbers.
SPARE = {"r": "".join(map(chr, range(0x20, 0x7F))), "b": "0123456789", "D": "0123456789", "T": "0123456789"}

# Paper and ink. The four tile colours are the Bauhaus primaries pulled toward
# the site's mint: teal, vermilion, ochre and plain ink (or paper in dark mode).
THEMES = {
    "dark": dict(
        bg="#0b0c0e", surface="#111316", panel="#0e1013", graphite="#191c21",
        line="#272a30", rule="#ece6da", ink="#ece6da", muted="#a29d92", faint="#6f6b63",
        accent="#00e6c3", soft="#6df3de", glow=0.12, mask_bg="#000000", mask_fg="#ece6da",
        tiles=(("#10c4a6", "#0b0c0e"), ("#ff6b3d", "#0b0c0e"), ("#f2c14e", "#0b0c0e"), ("#ece6da", "#0b0c0e")),
        heat=("#1a1d22", "#0d5d50", "#0aa88e", "#00e6c3"), grain=0,
    ),
    "light": dict(
        bg="#f3eee4", surface="#faf7f0", panel="#efe9dd", graphite="#e7e0d2",
        line="#d9d0bf", rule="#16161a", ink="#16161a", muted="#55524b", faint="#857f73",
        accent="#00735f", soft="#00a88f", glow=0.08, mask_bg="#16161a", mask_fg="#faf7f0",
        tiles=(("#00806a", "#fbf8f2"), ("#c8461f", "#fbf8f2"), ("#e9b12f", "#16161a"), ("#16161a", "#f3eee4")),
        heat=("#e6dfd0", "#9fd0c3", "#2f9c84", "#00735f"), grain=0.07,
    ),
}

BASE_CSS = (
    ".in{animation:rise .8s cubic-bezier(.23,1,.32,1) both}"
    "@keyframes rise{from{opacity:0;transform:translateY(10px)}}"
    ".fade{animation:fade .7s ease-out both}"
    "@keyframes fade{from{opacity:0}}"
    ".ping{transform-box:fill-box;transform-origin:center;animation:ping 2.2s cubic-bezier(0,0,.2,1) infinite}"
    "@keyframes ping{from{transform:scale(1);opacity:.75}to{transform:scale(3.2);opacity:0}}"
    ".grow{transform-box:fill-box;transform-origin:left center;animation:grow 1.1s cubic-bezier(.23,1,.32,1) both}"
    "@keyframes grow{from{transform:scaleX(0)}}"
    ".up{transform-box:fill-box;transform-origin:center bottom;animation:up .7s cubic-bezier(.23,1,.32,1) both}"
    "@keyframes up{from{transform:scaleY(0)}}"
    ".pop{transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.34,1.56,.64,1) both}"
    "@keyframes pop{from{opacity:0;transform:scale(.3)}}"
    ".wipe{transform-box:fill-box;transform-origin:center bottom;transform:scaleY(0);animation:wipe 1.6s cubic-bezier(.65,0,.35,1) .35s both}"
    "@keyframes wipe{from{transform:scaleY(1)}}"
    ".scan{opacity:0;animation:scan 1.6s cubic-bezier(.65,0,.35,1) .35s both}"
    "@keyframes scan{from{opacity:1;transform:translateY(0)}97%{opacity:1}to{opacity:0;transform:translateY(var(--h))}}"
    # Letters written in one at a time, each arriving in the accent colour (Svg.text stagger).
    ".ltr{animation:ltr .75s cubic-bezier(.23,1,.32,1) both}"
    "@keyframes ltr{from{opacity:0;transform:translateY(var(--rise));fill:var(--hl)}35%{fill:var(--hl)}}"
    # Counters (flipbook): each frame shows for its slot and the last one stays.
    ".fb{opacity:0;animation:fb linear}"
    "@keyframes fb{from,to{opacity:1}}"
    ".fbl{animation:fbl linear}"
    "@keyframes fbl{from,to{opacity:0}}"
    # A bar that grows to full length, holds, then shrinks to its value.
    ".cmp{transform-box:fill-box;transform-origin:left center;animation:cmp 2s both}"
    "@keyframes cmp{from{transform:scaleX(0);animation-timing-function:cubic-bezier(.23,1,.32,1)}"
    "35%,50%{transform:scaleX(var(--s));animation-timing-function:cubic-bezier(.65,0,.35,1)}to{transform:scaleX(1)}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
)


def n(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ---------------------------------------------------------------------- fonts

class Face:
    """Text layout shared by the two kinds of face below."""

    upm: int

    def name(self, ch: str) -> str:
        raise NotImplementedError

    def advance(self, ch: str) -> int:
        raise NotImplementedError

    def pair(self, left: str, right: str) -> int:
        raise NotImplementedError

    def outline(self, ch: str) -> str:
        raise NotImplementedError

    def layout(self, s: str, size: float, ls: float = 0) -> tuple[list[tuple[str, float]], float]:
        """Glyph offsets in font units, and the set width in pixels."""
        scale = size / self.upm
        out, x, prev = [], 0.0, None
        for ch in s:
            if prev is not None:
                x += self.pair(prev, ch) + ls / scale
            out.append((ch, x))
            x += self.advance(ch)
            prev = ch
        return out, x * scale


class Font(Face):
    """One static instance of a font: outlines, advances and pair kerning."""

    def __init__(self, path: Path, axes: dict[str, float]):
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer

        self.label = f"{path.name} {axes}"
        font = TTFont(path)
        if "fvar" in font:
            font = instancer.instantiateVariableFont(font, axes)
        self.upm = font["head"].unitsPerEm
        self.cmap = font.getBestCmap()
        self.glyphs = font.getGlyphSet()
        self.hmtx = font["hmtx"]
        self.pairs = self._kern_subtables(font)
        self.cache: dict[str, str] = {}

    @staticmethod
    def _kern_subtables(font: TTFont) -> list:
        if "GPOS" not in font:
            return []
        gpos = font["GPOS"].table
        lookups = sorted({i for fr in gpos.FeatureList.FeatureRecord if fr.FeatureTag == "kern"
                          for i in fr.Feature.LookupListIndex})
        subs = []
        for i in lookups:
            lookup = gpos.LookupList.Lookup[i]
            for st in lookup.SubTable:
                if lookup.LookupType == 9:
                    if st.ExtensionLookupType != 2:
                        continue
                    st = st.ExtSubTable
                elif lookup.LookupType != 2:
                    continue
                subs.append((st, {g: k for k, g in enumerate(st.Coverage.glyphs)}))
        return subs

    def kern(self, left: str, right: str) -> int:
        for st, cov in self.pairs:
            k = cov.get(left)
            if k is None:
                continue
            if st.Format == 1:
                for rec in st.PairSet[k].PairValueRecord:
                    if rec.SecondGlyph == right:
                        return getattr(rec.Value1, "XAdvance", 0) or 0
            else:
                c1 = st.ClassDef1.classDefs.get(left, 0)
                c2 = st.ClassDef2.classDefs.get(right, 0)
                return getattr(st.Class1Record[c1].Class2Record[c2].Value1, "XAdvance", 0) or 0
        return 0

    def name(self, ch: str) -> str:
        glyph = self.cmap.get(ord(ch))
        if glyph is None:
            raise SystemExit(f"{self.label} has no glyph for {ch!r}")
        return glyph

    def advance(self, ch: str) -> int:
        return self.hmtx[self.name(ch)][0]

    def pair(self, left: str, right: str) -> int:
        return self.kern(self.name(left), self.name(right))

    def outline(self, ch: str) -> str:
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.transformPen import TransformPen

        if ch not in self.cache:
            pen = SVGPathPen(self.glyphs, ntos=lambda v: str(round(v)))
            self.glyphs[self.name(ch)].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
            self.cache[ch] = pen.getCommands()
        return self.cache[ch]

    def export(self, chars: set[str]) -> dict:
        """What CachedFont needs to set `chars` exactly as this font does."""
        chars_ = sorted(chars)
        return {"upm": self.upm,
                "glyphs": {ch: [self.advance(ch), self.outline(ch)] for ch in chars_},
                "kern": {a + b: k for a in chars_ for b in chars_ if (k := self.pair(a, b))}}


class CachedFont(Face):
    """A face read from scripts/glyphs.json. It sets only the characters saved there."""

    def __init__(self, key: str, data: dict):
        self.label = f"face {key!r} in {GLYPHS.name}"
        self.upm = data["upm"]
        self.glyphs: dict[str, list] = data["glyphs"]
        self.kerns: dict[str, int] = data["kern"]

    def name(self, ch: str) -> str:
        if ch not in self.glyphs:
            raise SystemExit(f"{self.label} has no {ch!r}; rebuild on a machine with the fonts to add it")
        return ch

    def advance(self, ch: str) -> int:
        return self.glyphs[self.name(ch)][0]

    def pair(self, left: str, right: str) -> int:
        return self.kerns.get(left + right, 0)

    def outline(self, ch: str) -> str:
        return self.glyphs[self.name(ch)][1]


class Fonts:
    """Faces by key: the font files when FONT_DIR has them, else scripts/glyphs.json."""

    def __init__(self) -> None:
        self.loaded: dict[str, Face] = {}
        self.saved: dict | None = None

    def __getitem__(self, key: str) -> Face:
        if key not in self.loaded:
            file, axes = FACES[key]
            if (FONT_DIR / file).exists():
                self.loaded[key] = Font(FONT_DIR / file, axes)
            else:
                if self.saved is None:
                    if not GLYPHS.exists():
                        raise SystemExit(f"no {FONT_DIR / file} and no {GLYPHS}")
                    self.saved = json.loads(GLYPHS.read_text(encoding="utf-8"))["faces"]
                if key not in self.saved:
                    raise SystemExit(f"no {FONT_DIR / file}, and {GLYPHS.name} has no face {key!r}")
                self.loaded[key] = CachedFont(key, self.saved[key])
        return self.loaded[key]

    def from_files(self) -> bool:
        return all(isinstance(face, Font) for face in self.loaded.values())


def write_glyphs(fonts: Fonts, drawn: set[tuple[str, str]]) -> None:
    """Save every glyph the upstream card can need, for the daily rebuild on a
    runner without the fonts: what it drew today, the spares and the space."""
    chars: dict[str, set[str]] = defaultdict(set)
    for face, ch in drawn:
        chars[face].add(ch)
    for face, extra in SPARE.items():
        chars[face] |= set(extra)
    faces = {face: fonts[face].export(cs | {" "}) for face, cs in sorted(chars.items())}  # type: ignore[attr-defined]
    doc = {"about": "Outlines, advances and kerning for the characters assets/upstream-*.svg can use, exported "
                    "by scripts/build_assets.py from Cascadia Code (SIL OFL 1.1) and Sitka. The daily workflow "
                    "reads this file because its runner has neither font.",
           "faces": faces}
    GLYPHS.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                      encoding="utf-8", newline="\n")


# ------------------------------------------------------------------------ svg

class Svg:
    def __init__(self, fonts: Fonts, theme: dict, w: int, h: int, title: str, desc: str):
        self.fonts, self.t, self.w, self.h = fonts, theme, w, h
        self.title, self.desc = title, desc
        self.body: list[str] = []
        self.defs: list[str] = []
        self.css: list[str] = [BASE_CSS]
        self.used: set[tuple[str, str]] = set()
        self.t0 = 0.0  # seconds after load when this card starts; rise() adds it to every delay

    def c(self, color: str) -> str:
        return self.t.get(color, color)

    def add(self, *parts: str) -> None:
        self.body.extend(parts)

    def width(self, s: str, size: float, face: str = "r", ls: float = 0) -> float:
        return self.fonts[face].layout(s, size, ls)[1]

    def wrap(self, s: str, size: float, width: float, face: str = "T") -> list[str]:
        lines, cur = [], ""
        for word in s.split():
            trial = f"{cur} {word}" if cur else word
            if cur and self.width(trial, size, face) > width:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        return lines + [cur] if cur else lines

    def text(self, s: str, x: float, y: float, size: float, face: str = "r", fill: str = "ink",
             anchor: str = "start", ls: float = 0, cls: str = "", op: float | None = None,
             stagger: tuple[float, float] | None = None) -> str:
        """Outline text. `cls` may animate fill or opacity but never transform,
        because the group's transform attribute places the glyphs. `stagger`
        (first delay, step) writes the letters in one at a time."""
        font = self.fonts[face]
        glyphs, width = font.layout(s, size, ls)
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
        uses = []
        for ch, gx in glyphs:
            if ch == " ":
                continue
            self.used.add((face, ch))
            anim = ""
            if stagger:
                anim = f' class="ltr" style="animation-delay:{n(stagger[0] + len(uses) * stagger[1])}s"'
            uses.append(f'<use href="#g{face}_{ord(ch):x}" x="{round(gx)}"{anim}/>')
        attrs = f' class="{cls}"' if cls else ""
        if op is not None:
            attrs += f' opacity="{n(op)}"'
        if stagger:
            # Each letter rises 14 px. Inside the group one unit is one font unit, not one pixel.
            attrs += f' style="--hl:{self.c("accent")};--rise:{n(14 * font.upm / size)}px"'
        return (f'<g{attrs} fill="{self.c(fill)}" transform="translate({n(x)} {n(y)}) '
                f'scale({size / font.upm:.6f})">{"".join(uses)}</g>')

    def pulse(self, d: str, length: float, dur: float, delay: float, color: str = "accent",
              width: float = 2.4, dash: float = 12, travel: float = 0.5) -> str:
        """A bright dash that runs along `d` once per `dur` seconds."""
        dash = min(dash, length * 0.6)
        name = f"pl{round(dash)}_{round(length)}_{round(travel * 100)}"
        kf = f"@keyframes {name}{{0%{{stroke-dashoffset:{n(dash)}}}{n(travel * 100)}%,100%{{stroke-dashoffset:{n(-length)}}}}}"
        if kf not in self.css:
            self.css.append(kf)
        return (f'<path d="{d}" fill="none" stroke="{self.c(color)}" stroke-width="{n(width)}" '
                f'stroke-linecap="round" stroke-dasharray="{n(dash)} {n(length + dash)}" '
                f'stroke-dashoffset="{n(dash)}" style="animation:{name} {n(dur)}s linear {n(delay)}s infinite"/>')

    def render(self) -> str:
        glyph_defs = "".join(
            f'<path id="g{face}_{ord(ch):x}" d="{self.fonts[face].outline(ch)}"/>' for face, ch in sorted(self.used)
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="title desc">'
            f'<title id="title">{escape(self.title)}</title><desc id="desc">{escape(self.desc)}</desc>'
            f'<style>{"".join(self.css)}</style>'
            f'<defs>{"".join(self.defs)}{glyph_defs}</defs>{"".join(self.body)}</svg>'
        )


# ---------------------------------------------------------------- shared bits

def paper(s: Svg, fill: str = "bg", rx: float = 18) -> None:
    """Card background: flat paper (or ink), a hairline border and, in the light
    theme, a faint print grain."""
    t = s.t
    s.defs.append(f'<clipPath id="frame"><rect width="{s.w}" height="{s.h}" rx="{rx}"/></clipPath>')
    layers = f'<rect width="{s.w}" height="{s.h}" fill="{s.c(fill)}"/>'
    if t["grain"]:
        s.defs.append('<filter id="grain" x="0" y="0" width="100%" height="100%">'
                      '<feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" stitchTiles="stitch"/>'
                      '<feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.4 1"/></filter>')
        layers += f'<rect width="{s.w}" height="{s.h}" filter="url(#grain)" opacity="{t["grain"]}"/>'
    s.add(f'<g clip-path="url(#frame)">{layers}</g>',
          f'<rect x=".5" y=".5" width="{s.w - 1}" height="{s.h - 1}" rx="{rx - .5}" fill="none" stroke="{t["line"]}"/>')


def chips(s: Svg, items: list[str], x: float, y: float, size: float = 11.5, delay: float | None = None) -> float:
    t = s.t
    h, pad = 24, 9
    out = []
    for item in items:
        w = s.width(item, size) + pad * 2
        out.append(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{h}" rx="4" fill="none" stroke="{t["line"]}"/>')
        out.append(s.text(item, x + pad, y + 16.2, size, fill="muted"))
        x += w + 8
    if delay is None:
        s.add(*out)
    else:
        rise(s, delay, *out)
    return x - 8


def box(s: Svg, x: float, y: float, w: float, h: float, label: str, sub: str = "",
        hl: bool = False, size: float = 11.5, dashed: bool = False) -> str:
    t = s.t
    stroke = t["accent"] if hl else t["line"]
    dash = ' stroke-dasharray="4 4"' if dashed else ""
    parts = [f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="5" '
             f'fill="{t["panel"]}" stroke="{stroke}"{dash}/>']
    cx = x + w / 2
    if sub:
        parts.append(s.text(label, cx, y + h / 2 - 2, size, "b", "accent" if hl else "ink", anchor="middle"))
        parts.append(s.text(sub, cx, y + h / 2 + 12, 10, fill="muted", anchor="middle"))
    else:
        parts.append(s.text(label, cx, y + h / 2 + size * .36, size, "b", "accent" if hl else "ink", anchor="middle"))
    return "".join(parts)


def rise(s: Svg, delay: float, *parts: str, cls: str = "in") -> None:
    """Fade the parts in, rising slightly, `delay` seconds after the card starts (s.t0)."""
    s.add(f'<g class="{cls}" style="animation-delay:{n(s.t0 + delay)}s">{"".join(parts)}</g>')


def label(s: Svg, text: str, x: float, y: float, fill: str = "accent", size: float = 11, anchor: str = "start") -> str:
    return s.text(text, x, y, size, "m", fill, anchor=anchor, ls=1.3)


# Motion. A README image can't see the page scroll: every animation starts when
# its image loads. So sections lower on the page start later, and a reader who
# scrolls at an ordinary pace meets each one while it plays. Seconds after load:
T_IMPACT = .5      # the tiles rise; their counters run from 1.1 s to about 3.5 s
T_UPSTREAM = 2.4   # the header; the squares fill and the total counts up from 3 s to about 5.2 s
T_VAANI = 3.2      # then the chat reel loops
T_CORTEX = 3.8
T_PROJECTS = 4.4

EASE_OUT = (.23, 1, .32, 1)     # .in, .grow and .up
EASE_IN_OUT = (.65, 0, .35, 1)  # .wipe and the shrink in .cmp


def bezier(p: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """CSS cubic-bezier(): the share of the change done when share p of the time has passed."""
    lo, hi = 0.0, 1.0
    for _ in range(32):
        u = (lo + hi) / 2
        if 3 * (1 - u) ** 2 * u * x1 + 3 * (1 - u) * u ** 2 * x2 + u ** 3 < p:
            lo = u
        else:
            hi = u
    return 3 * (1 - lo) ** 2 * lo * y1 + 3 * (1 - lo) * lo ** 2 * y2 + lo ** 3


def ramp(v0: int, v1: int, start: float, dur: float, curve: tuple = EASE_OUT,
         steps: int = 24) -> list[tuple[float, int]]:
    """(time, value) for a counter going from v0 to v1 in step with a bar animated
    on `curve`, sampled the way a script-driven counter would be."""
    shots = [(0.0, v0)]
    for k in range(1, steps + 1):
        v = round(v0 + (v1 - v0) * bezier(k / steps, *curve))
        if v != shots[-1][1]:
            shots.append((start + dur * k / steps, v))
    return shots


def flipbook(shots: list[tuple[float, str]]) -> str:
    """Show each (start time, svg) until the next one starts, and keep the last.
    With reduced motion only the last is drawn."""
    ms = [round(t * 1000) for t, _ in shots]
    out = []
    for i, (_, svg) in enumerate(shots):
        if i + 1 == len(shots):
            out.append(f'<g class="fbl" style="animation-duration:{ms[i]}ms">{svg}</g>')
        elif ms[i + 1] > ms[i]:
            out.append(f'<g class="fb" style="animation-duration:{ms[i + 1] - ms[i]}ms;'
                       f'animation-delay:{ms[i]}ms">{svg}</g>')
    return "".join(out)


# ------------------------------------------------------------------ masthead

def portrait(s: Svg, x0: float, y0: float, size: float) -> None:
    """Halftone of scripts/portrait.txt: one dot per cell, sized by tone, on an
    offset grid. Ink dots on paper; on ink, light dots sized by lightness."""
    t = s.t
    rows = PORTRAIT.read_text(encoding="utf-8").split()
    grid = len(rows)
    cell = size / grid
    dark_theme = t is THEMES["dark"]
    dots = []
    for r, row in enumerate(rows):
        shift = cell / 2 if r % 2 else 0
        # Fade the shoulders out over the bottom quarter, like a cut-out photo.
        fade = min(1.0, max(0.3, 1 - (r / grid - 0.72) / 0.28 * 0.7))
        for c, v in enumerate(row):
            if v == ".":
                continue
            dark = int(v, 16) / 15
            if dark_theme:
                tone = (1 - dark) ** 1.5 * fade
                rad = cell * 0.56 * tone ** 0.5
            else:
                tone = 0.04 + 0.96 * dark ** 1.45
                rad = cell * 0.62 * tone ** 0.5
            if rad < 0.35:
                continue
            dots.append(f'<circle cx="{n(x0 + (c + .5) * cell + shift)}" cy="{n(y0 + (r + .5) * cell)}" r="{n(rad)}"/>')
    s.defs.append(f'<clipPath id="pclip"><rect x="{n(x0)}" y="{n(y0)}" width="{n(size)}" height="{n(size)}"/></clipPath>')
    s.add(f'<rect x="{n(x0)}" y="{n(y0)}" width="{n(size)}" height="{n(size)}" fill="{t["panel"]}"/>',
          f'<g clip-path="url(#pclip)" fill="{t["ink"]}">{"".join(dots)}</g>',
          # The press: a cover that lifts top to bottom, with a mint line riding its edge.
          f'<rect class="wipe" x="{n(x0)}" y="{n(y0)}" width="{n(size)}" height="{n(size)}" fill="{t["panel"]}"/>',
          f'<rect class="scan" style="--h:{n(size)}px" x="{n(x0)}" y="{n(y0)}" width="{n(size)}" height="1.6" fill="{t["accent"]}"/>',
          f'<rect x="{n(x0 + .5)}" y="{n(y0 + .5)}" width="{n(size - 1)}" height="{n(size - 1)}" fill="none" stroke="{t["line"]}"/>')


MASTHEAD_TEXT = ("I build AI agents on local models and test them against live conversations, not only "
                 "unit tests. Previously GenAI engineer at ReinHealth, a healthcare AI startup.")


def masthead(fonts: Fonts, theme: str) -> Svg:
    s = Svg(fonts, THEMES[theme], 1000, 376, "Roydon Sequeira, AI Agent Developer",
            "AI Agent Developer at Code Crew Studio. I build AI agents on local models and test them against "
            "live conversations. Previously GenAI engineer at ReinHealth, a healthcare AI startup. Based in Udupi, "
            "India. Open to AI engineering roles and contracts.")
    t = s.t
    lines = s.wrap(MASTHEAD_TEXT, 15.5, 600)
    s.h = max(376, 290 + len(lines) * 22 + 46)
    paper(s)
    rise(s, 0, label(s, "ROYDONSEQUEIRA.COM", 44, 40, "faint"),
         label(s, "UDUPI, IN · UTC+05:30", 956, 40, "faint", anchor="end"))
    s.add(f'<rect class="grow" x="44" y="52" width="912" height="2.4" fill="{t["rule"]}"/>',
          f'<rect class="grow" x="44" y="58" width="912" height="1" fill="{t["rule"]}" style="animation-delay:.12s"/>')

    rise(s, .1, label(s, "AI AGENT DEVELOPER · CODE CREW STUDIO", 44, 100, size=11.5))
    # The name is written in letter by letter, each letter arriving in the accent colour.
    s.add(s.text("Roydon", 38, 178, 84, "Di", stagger=(.2, .07)),
          s.text("Sequeira", 100, 254, 84, "Di", stagger=(.2 + 6 * .07 + .05, .07)))
    rise(s, .9, *[s.text(line, 44, 296 + i * 22, 15.5, "T", "muted") for i, line in enumerate(lines)])
    sy = 296 + len(lines) * 22 + 18
    rise(s, 1.1,
         f'<circle class="ping" cx="49" cy="{sy - 4.5}" r="4.5" fill="{t["accent"]}" opacity="0"/>',
         f'<circle cx="49" cy="{sy - 4.5}" r="4.5" fill="{t["accent"]}"/>',
         s.text("Open to AI engineering roles and contracts", 64, sy, 12.5, fill="muted"))
    portrait(s, 676, 82, 268)
    return s


# -------------------------------------------------------------------- impact

# (tag, prefix, number, unit, caption, mini chart, chart value). The prefix and
# unit are set small and italic so the number carries the tile.
IMPACT = [
    ("REINHEALTH · PROD", "~", "70", "%", "less manual patient-intake work, estimated", "bar", .70),
    ("REINHEALTH · PROD", "<", "5", " min", "patient intake, down from 15 minutes", "compare", 5 / 15),
    ("LOCAL MODELS ONLY", "", "0", "", "patient records sent to outside APIs", "dots", 1),
    ("CORTEX · LIVE TESTS", "", "27", "", "bugs found in 187 live conversations", "count", 27),
]


def impact(fonts: Fonts, theme: str) -> Svg:
    s = Svg(fonts, THEMES[theme], 1000, 236, "Impact",
            "About 70% less manual patient-intake work (estimated). Patient intake down from 15 minutes to under 5. "
            "Zero patient records sent to outside APIs. 27 bugs in CORTEX found by 187 live conversations "
            "that its unit tests had missed.")
    tile_w, gap, tally = 241, 12, .045
    for i, (tag, prefix, num, unit, caption, viz, frac) in enumerate(IMPACT):
        fill, ink = s.t["tiles"][i]
        x = i * (tile_w + gap)
        ix, iw = x + 20, tile_w - 40
        # The tile rises at t_in; its mini chart and counter run from d, one tile after another.
        t_in, d = T_IMPACT + i * .15, T_IMPACT + .6 + i * .35
        # "~" sits high like an approximation mark; "<" sits on the line.
        psize, py = (38, 100) if prefix == "~" else (50, 120)
        nx = ix - 2 + (s.width(prefix, psize, "Di") + 3 if prefix else 0)

        def shown(v: int, with_prefix: bool = True) -> str:
            out = [s.text(prefix, ix - 2, py, psize, "Di", ink)] if prefix and with_prefix else []
            out.append(s.text(str(v), nx, 128, 86, "D", ink))
            if unit:
                out.append(s.text(unit, nx + s.width(str(v), 86, "D") + 2, 128, 40 if unit == "%" else 30, "Di", ink))
            return "".join(out)

        value = int(num)
        if viz == "bar":
            number = flipbook([(at, shown(v)) for at, v in ramp(0, value, d, 1.1)])
        elif viz == "compare":
            # Counts down from the old figure while the bar shrinks; "<" arrives with the final value.
            shots = ramp(round(value / frac), value, d + 1.0, 1.0, EASE_IN_OUT, steps=20)
            number = flipbook([(at, shown(v, k == len(shots) - 1)) for k, (at, v) in enumerate(shots)])
        elif viz == "count":
            number = flipbook([(0.0, shown(0))] + [(d + k * tally, shown(k + 1)) for k in range(value)])
        else:
            number = shown(value)
        parts = [f'<rect x="{x}" y="0" width="{tile_w}" height="236" rx="8" fill="{fill}"/>',
                 s.text(tag, ix, 34, 10.5, "m", ink, ls=1.3, op=.8), number]
        for j, line in enumerate(s.wrap(caption, 15, iw)):
            parts.append(s.text(line, ix, 162 + j * 20, 15, "T", ink))

        by = 212
        if viz == "bar":
            parts += [f'<rect x="{ix}" y="{by}" width="{iw}" height="5" rx="2.5" fill="{ink}" opacity=".22"/>',
                      f'<rect class="grow" x="{ix}" y="{by}" width="{n(iw * frac)}" height="5" rx="2.5" fill="{ink}" '
                      f'style="animation-delay:{n(d)}s"/>']
        elif viz == "compare":
            # The faint bar is the old 15 minutes; the solid one grows to it, then shrinks to a third.
            parts += [f'<rect class="grow" x="{ix}" y="{by - 4}" width="{iw}" height="4" rx="2" fill="{ink}" opacity=".3" '
                      f'style="animation-delay:{n(d)}s"/>',
                      f'<rect class="cmp" x="{ix}" y="{by + 4}" width="{n(iw * frac)}" height="4" rx="2" fill="{ink}" '
                      f'style="--s:{n(1 / frac)};animation-delay:{n(d)}s"/>']
        elif viz == "dots":
            parts += [f'<rect class="pop" x="{n(ix + k * iw / 14)}" y="{by - 2}" width="9" height="9" rx="2" '
                      f'fill="none" stroke="{ink}" style="animation-delay:{n(d + k * .04)}s"/>' for k in range(14)]
        elif viz == "count":
            pitch = iw / frac
            parts += [f'<rect class="pop" x="{n(ix + k * pitch)}" y="{by - 2}" width="{n(pitch - 2.2)}" height="9" rx="1" '
                      f'fill="{ink}" style="animation-delay:{n(d + k * tally)}s"/>' for k in range(int(frac))]
        rise(s, t_in, *parts)
    return s


# ------------------------------------------------------------------ upstream

def github(path: str, token: str) -> dict:
    req = urllib.request.Request(f"https://api.github.com{path}", headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"{USER}-profile-assets",
        "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def merged_upstream() -> tuple[list[tuple[str, date]], int]:
    """Merged pull requests in other people's repositories, and the open count."""
    token = os.environ.get("GITHUB_TOKEN") or subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    merged, page = [], 1
    while True:
        # is:public: a local token can also see private repositories, which stay off the chart.
        q = urllib.parse.quote(f"is:pr is:public is:merged author:{USER} -user:{USER}")
        res = github(f"/search/issues?q={q}&per_page=100&page={page}", token)
        for item in res["items"]:
            repo = item["repository_url"].split("/repos/", 1)[1]
            merged.append((repo, date.fromisoformat(item["pull_request"]["merged_at"][:10])))
        if len(res["items"]) < 100:
            break
        page += 1
    q = urllib.parse.quote(f"is:pr is:public is:open author:{USER} -user:{USER}")
    return merged, github(f"/search/issues?q={q}&per_page=1", token)["total_count"]


def upstream_summary(data: tuple[list[tuple[str, date]], int]) -> str:
    merged, open_count = data
    by_repo = Counter(repo for repo, _ in merged)
    first = min(d for _, d in merged)
    repos = sorted(by_repo.items(), key=lambda kv: (-kv[1], kv[0]))
    return (f"{len(merged)} pull requests merged into {len(repos)} open-source projects since "
            f"{first:%B} {first.day}, {first.year}, with {open_count} more open: "
            + "; ".join(f"{r} {k}" for r, k in repos) + ".")


def write_upstream_block(data: tuple[list[tuple[str, date]], int], today: date) -> None:
    """Keep the README's alt text and date in step with the chart."""
    start, end = "<!-- upstream:start -->", "<!-- upstream:end -->"
    alt = escape(upstream_summary(data), {'"': "&quot;"})
    block = "\n".join([
        start,
        f'<a href="{SEARCH}">',
        "  <picture>",
        '    <source media="(prefers-color-scheme: dark)" srcset="assets/upstream-dark.svg">',
        '    <source media="(prefers-color-scheme: light)" srcset="assets/upstream-light.svg">',
        f'    <img alt="{alt}" src="assets/upstream-dark.svg" width="100%">',
        "  </picture>",
        "</a>",
        "",
        '<sub>Refreshed daily from the GitHub search API by <a href=".github/workflows/readme-sync.yml">'
        f"readme-sync</a>. Counts as of {today:%Y-%m-%d}; the chart links to the live list of every merged "
        "pull request.</sub>",
        end,
    ])
    text = README.read_text(encoding="utf-8")
    i, j = text.find(start), text.find(end)
    if i < 0 or j < 0:
        raise SystemExit(f"README.md needs {start} ... {end} markers")
    README.write_text(text[:i] + block + text[j + len(end):], encoding="utf-8", newline="\n")


WINDOW_WEEKS = 8  # the squares cover the last eight weeks; the counts cover every merge
MAX_ROWS = 10     # past this many projects, the ones with the fewest merges share the last row


def upstream(fonts: Fonts, theme: str, data: tuple[list[tuple[str, date]], int], today: date) -> Svg:
    merged, open_count = data
    by_repo = Counter(repo for repo, _ in merged)
    ranked = [r for r, _ in sorted(by_repo.items(), key=lambda kv: (-kv[1], kv[0]))]
    repos = ranked if len(ranked) <= MAX_ROWS else (
        ranked[:MAX_ROWS - 1] + [f"{len(ranked) - MAX_ROWS + 1} more projects"])
    row_of = {repo: min(i, len(repos) - 1) for i, repo in enumerate(ranked)}
    row_total: Counter = Counter()
    for repo, k in by_repo.items():
        row_total[row_of[repo]] += k
    first = min(d for _, d in merged)
    first_week = first - timedelta(days=first.weekday())  # the Monday of the first week
    start = max(first_week, today - timedelta(days=today.weekday(), weeks=WINDOW_WEEKS - 1))
    days = (today - start).days + 1
    cells: dict[tuple[int, int], int] = defaultdict(int)
    per_day: Counter = Counter()
    for repo, d in merged:
        if d >= start:
            k = min((d - start).days, days - 1)
            cells[(row_of[repo], k)] += 1
            per_day[k] += 1
    earlier = len(merged) - sum(per_day.values())  # merged before the first square

    row_h, top = 19, 168
    h = top + len(repos) * row_h + 74
    s = Svg(fonts, THEMES[theme], 1000, h, "Merged upstream", upstream_summary(data))
    t = s.t
    paper(s, "surface", rx=16)
    gx0, gx1 = 236, 930
    pitch = (gx1 - gx0) / days
    size = min(pitch - 3, 13)

    rise(s, T_UPSTREAM, label(s, "OPEN SOURCE · OTHER PEOPLE'S REPOS", 32, 44),
         s.text("Merged upstream", 30, 96, 42, "Di"),
         s.text(f"Pull requests in {len(repos)} projects since {first:%b} {first.day}, "
                f"with {open_count} more in review", 32, 126, 15, "T", "muted"))
    # The squares fill left to right, day k at fill_at + k * step. The total counts
    # each day's merges as its column lands, and spreads older merges across the fill.
    fill_at, step = T_UPSTREAM + .6, min(.045, 2.2 / days)
    running, shots = 0, [(0.0, 0)]
    for k in range(days):
        running += per_day.get(k, 0)
        v = running + round(earlier * (k + 1) / days)
        if v != shots[-1][1]:
            shots.append((fill_at + k * step, v))
    rise(s, T_UPSTREAM + .1, flipbook([(at, s.text(str(v), 968, 100, 76, "D", anchor="end")) for at, v in shots]),
         label(s, "MERGED", 968, 127, "faint", size=10.5, anchor="end"))

    # Pull requests merged per day, the busiest day in vermilion.
    peak = max(per_day.values(), default=0)
    bars = []
    for k in range(days):
        v = per_day.get(k, 0)
        if not v:
            continue
        bh = 22 * v / peak
        color = t["tiles"][1][0] if v == peak else t["faint"]
        bars.append(f'<rect class="up" x="{n(gx0 + k * pitch + (pitch - size) / 2)}" y="{n(top - 8 - bh)}" '
                    f'width="{n(size)}" height="{n(bh)}" fill="{color}" style="animation-delay:{n(fill_at + k * step)}s"/>')
    s.add(*bars)

    heat, names = t["heat"], []
    for r, repo in enumerate(repos):
        y = top + r * row_h
        names += [s.text(repo, 32, y + size - 2, 11.5, fill="muted"),
                  s.text(str(row_total[r]), 968, y + size - 2, 12, "b", anchor="end")]
        for k in range(days):
            v = cells.get((r, k), 0)
            x = gx0 + k * pitch + (pitch - size) / 2
            if v:
                s.add(f'<rect class="pop" x="{n(x)}" y="{y}" width="{n(size)}" height="{n(size)}" rx="2" '
                      f'fill="{heat[min(v, 3)]}" style="animation-delay:{n(fill_at + k * step)}s"/>')
            else:
                s.add(f'<rect x="{n(x)}" y="{y}" width="{n(size)}" height="{n(size)}" rx="2" fill="{heat[0]}"/>')
    rise(s, T_UPSTREAM + .2, *names)

    axis_y = top + len(repos) * row_h + 14
    for k in range(0, days, 7):
        d = start + timedelta(days=k)
        x = gx0 + k * pitch + pitch / 2
        s.add(f'<rect x="{n(x - .5)}" y="{axis_y - 11}" width="1" height="5" fill="{t["line"]}"/>',
              s.text(f"{d:%b} {d.day}".upper(), x, axis_y + 6, 10, fill="faint", anchor="middle"))

    foot = h - 22
    key = "ONE SQUARE PER PROJECT PER DAY ·"
    if start > first_week:
        key = f"LAST {WINDOW_WEEKS} WEEKS · {key}"
    s.add(s.text(key, 32, foot, 10, fill="faint", ls=.6))
    lx = 32 + s.width(key, 10, ls=.6) + 12
    for lvl, word in enumerate(("0", "1", "2", "3+ MERGED")):
        s.add(f'<rect x="{n(lx)}" y="{foot - 9.5}" width="11" height="11" rx="2" fill="{heat[lvl]}"/>',
              s.text(word, lx + 15, foot, 10, fill="faint"))
        lx += 15 + s.width(word, 10) + 12
    s.add(s.text(f"GITHUB SEARCH API · {today:%Y-%m-%d}", 968, foot, 10, fill="faint", anchor="end", ls=.6))
    return s


# ------------------------------------------------------------------ projects

def cortex_card(fonts: Fonts, theme: str) -> Svg:
    s = Svg(fonts, THEMES[theme], 1000, 344, "CORTEX, Private Intelligence Framework",
            "A private AI agent that runs entirely on your own machine: planning, sandboxed tools, "
            "four-tier memory, streaming UI and OpenTelemetry tracing, powered by Ollama.")
    t = s.t
    s.t0 = T_CORTEX
    paper(s, "surface", rx=16)
    x0 = 32
    rise(s, 0, label(s, "FLAGSHIP · OPEN SOURCE · MIT", x0, 44, size=11.5),
         s.text("CORTEX", x0, 98, 44, "b"),
         s.text("Private Intelligence Framework", x0 + s.width("CORTEX", 44) + 18, 97, 29, "Di"))
    desc = ("A private AI agent that runs entirely on your own machine: it plans, uses sandboxed tools, "
            "remembers you across sessions and streams every step, on a 6 GB laptop GPU. No cloud, no API keys.")
    rise(s, .1, *[s.text(line, x0, 134 + j * 23, 16, "T", "muted") for j, line in enumerate(s.wrap(desc, 16, 556))])
    feats = ["4-tier memory: working · episodic · semantic · procedural",
             "LATS tree search + supervisor-worker orchestration",
             "guardrails enforced in code, not prompts",
             "OpenTelemetry spans on every model, tool and memory call"]
    for j, f in enumerate(feats):
        rise(s, .2 + j * .06, s.text("▸", x0, 212 + j * 22, 13.5, fill="accent"), s.text(f, x0 + 18, 212 + j * 22, 13))
    chips(s, ["Python 3.12", "FastAPI", "Next.js", "ChromaDB", "Ollama", "OpenTelemetry"], x0, 300, delay=.3)
    rise(s, .35, s.text("roydonsequeira/CORTEX-Private-Intelligence-Framework →", 968, 318, 12, fill="accent", anchor="end"))

    # Architecture: UI → API → kernel → memory / tools / router → Ollama.
    mid, period = 784, 3.0
    edges = [
        (f"M{mid} 54V78", 24, 0),
        (f"M{mid} 106V130", 24, .3),
        (f"M{mid} 172V184H676V196", 12 + 108 + 12, .6),
        (f"M{mid} 172V196", 24, .6),
        (f"M{mid} 172V184H892V196", 12 + 108 + 12, .6),
        ("M892 236V262", 26, 1.0),
    ]
    arch = [f'<path d="{d}" fill="none" stroke="{t["line"]}" stroke-width="1.2"/>' for d, _, _ in edges]
    arch.append(f'<path d="M676 236V262M784 236V262" fill="none" stroke="{t["line"]}" stroke-width="1.2" stroke-dasharray="3 4"/>')
    arch += [s.pulse(d, length, period, delay, dash=10, travel=.22) for d, length, delay in edges]
    arch += [
        box(s, 719, 26, 130, 28, "NEXT.JS UI"),
        box(s, 719, 78, 130, 28, "FASTAPI · SSE"),
        box(s, 684, 130, 200, 42, "AGENT KERNEL", "plan · act · reflect · LATS", hl=True),
        box(s, 626, 196, 100, 40, "MEMORY", "sqlite · chroma"),
        box(s, 734, 196, 100, 40, "TOOLS", "sandboxed"),
        box(s, 842, 196, 100, 40, "ROUTER", "model routing"),
        box(s, 626, 262, 208, 28, "OTEL → JAEGER", dashed=True, size=11),
        box(s, 842, 262, 100, 28, "OLLAMA", hl=True),
    ]
    rise(s, .15, *arch, cls="fade")
    return s


def half_card(fonts: Fonts, theme: str, title: str, tag: str, desc: str, stack: list[str], a11y: str,
              t0: float = T_PROJECTS) -> Svg:
    s = Svg(fonts, THEMES[theme], 490, 300, title, a11y)
    s.t0 = t0
    paper(s, "surface", rx=16)
    rise(s, 0, label(s, tag, 28, 40),
         s.text("→", 462, 40, 14, "b", "accent", anchor="end"),
         s.text(title, 26, 82, 33, "D"))
    rise(s, .1, *[s.text(line, 28, 110 + j * 21, 15, "T", "muted") for j, line in enumerate(s.wrap(desc, 15, 434))])
    if stack:
        chips(s, stack, 28, 258, delay=.3)
    return s


def rag_card(fonts: Fonts, theme: str) -> Svg:
    s = half_card(fonts, theme, "RagChatbot", "RAG · OPEN SOURCE",
                  "Chat with your own PDFs, scans and Word files, entirely on your machine. OCR ingestion, "
                  "local embeddings, streamed answers.",
                  ["FastAPI", "LangChain", "ChromaDB", "EasyOCR", "Next.js"],
                  "Local RAG chatbot: Ollama LLM, ChromaDB vector store, OCR and PDF ingestion, Next.js UI.")
    t = s.t
    stages = ["DOCS", "OCR", "EMBED", "CHROMA", "LLM"]
    bw, gap, y = 70, 21, 180
    x_first, x_last = 28 + bw / 2, 28 + 4 * (bw + gap) + bw / 2
    length = x_last - x_first
    period = 3.2
    parts = [f'<path d="M{n(x_first)} {y + 15}H{n(x_last)}" stroke="{t["line"]}" stroke-width="1.2"/>',
             s.pulse(f"M{n(x_first)} {y + 15}H{n(x_last)}", length, period, 0, dash=26, travel=.7, width=3)]
    for i, st in enumerate(stages):
        x = 28 + i * (bw + gap)
        hit = (x + bw / 2 - x_first) / length * .7
        s.css.append(f"@keyframes rg{i}{{0%,{n(max(hit * 100 - 4, 0))}%{{stroke:{t['line']}}}"
                     f"{n(hit * 100 + 2)}%{{stroke:{t['accent']}}}{n(min(hit * 100 + 20, 100))}%,100%{{stroke:{t['line']}}}}}")
        parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="30" rx="5" fill="{t["panel"]}" stroke="{t["line"]}" '
                     f'style="animation:rg{i} {period}s linear infinite"/>')
        parts.append(s.text(st, x + bw / 2, y + 19, 11, "b", "accent" if i == 4 else "ink", anchor="middle"))
    parts.append(s.text("SSE token stream → answer grounded in your files", 28, 234, 11, fill="faint"))
    rise(s, .2, *parts, cls="fade")
    return s


def soap_card(fonts: Fonts, theme: str) -> Svg:
    s = half_card(fonts, theme, "Clinical SOAP Notes", "HEALTHCARE · n8n · OPEN SOURCE",
                  "Text or voice in, structured SOAP note out. Three n8n workflows (TTT, STT, TTS) on a local LLM.",
                  ["n8n", "Ollama · Gemma 3", "ElevenLabs", "PostgreSQL"],
                  "n8n workflows that turn clinical text or voice into structured SOAP notes with a local LLM.",
                  t0=T_PROJECTS + .15)
    t = s.t
    words = ["subjective", "objective", "assessment", "plan"]
    tw_, gap, y = 96, 16, 158
    period = 4.8
    parts = []
    for i, (letter, word) in enumerate(zip("SOAP", words)):
        fill, ink = t["tiles"][i]
        x = 28 + i * (tw_ + gap)
        on, hold = i * 12 + 4, 78
        s.css.append(f"@keyframes sp{i}{{0%,{on}%{{fill:{t['panel']};stroke:{t['line']}}}"
                     f"{on + 5}%,{hold}%{{fill:{fill};stroke:{fill}}}{hold + 8}%,100%{{fill:{t['panel']};stroke:{t['line']}}}}}"
                     f"@keyframes sl{i}{{0%,{on}%{{fill:{t['ink']}}}{on + 5}%,{hold}%{{fill:{ink}}}{hold + 8}%,100%{{fill:{t['ink']}}}}}"
                     f".sl{i}{{animation:sl{i} {period}s ease-in-out infinite}}")
        parts.append(f'<rect x="{x}" y="{y}" width="{tw_}" height="54" rx="5" fill="{t["panel"]}" stroke="{t["line"]}" '
                     f'style="animation:sp{i} {period}s ease-in-out infinite"/>')
        parts.append(s.text(letter, x + tw_ / 2, y + 40, 36, "D", anchor="middle", cls=f"sl{i}"))
        parts.append(s.text(word, x + tw_ / 2, y + 74, 11, fill="muted", anchor="middle"))
    rise(s, .2, *parts, cls="fade")
    return s


BLOB = "M0 -24C14 -26 28 -14 26 0C25 14 12 26 -2 24C-16 22 -28 12 -26 -2C-24 -16 -13 -22 0 -24Z"


def lesion_card(fonts: Fonts, theme: str) -> Svg:
    s = half_card(fonts, theme, "Skin Lesion Segmentation", "COMPUTER VISION · OPEN SOURCE",
                  "U-Net (PyTorch) vs ResU-Net (TensorFlow 2) on 2,594 ISIC 2018 dermoscopy images, with a Streamlit demo.",
                  ["PyTorch", "TensorFlow", "OpenCV", "Streamlit"],
                  "Skin lesion segmentation on ISIC 2018 using U-Net in PyTorch and ResU-Net in TensorFlow 2.",
                  t0=T_PROJECTS + .35)
    t = s.t
    pw, ph, y = 118, 66, 158
    gap = (434 - 3 * pw) / 2
    s.defs.append(f'<radialGradient id="lesion" cx=".45" cy=".45" r=".6"><stop offset="0" stop-color="{t["accent"]}" stop-opacity=".95"/>'
                  f'<stop offset="1" stop-color="{t["soft"]}" stop-opacity=".35"/></radialGradient>')
    s.css.append("@keyframes trace{0%{stroke-dashoffset:100}45%,85%{stroke-dashoffset:0}100%{stroke-dashoffset:-100}}")
    parts = []
    names = ["dermoscopy", "predicted mask", "contour"]
    for i in range(3):
        x = 28 + i * (pw + gap)
        cx, cy = x + pw / 2, y + ph / 2
        fill = t["mask_bg"] if i == 1 else t["panel"]
        parts.append(f'<rect x="{n(x)}" y="{y}" width="{pw}" height="{ph}" rx="5" fill="{fill}" stroke="{t["line"]}"/>')
        if i == 0:
            parts.append(f'<path d="{BLOB}" transform="translate({n(cx)} {cy})" fill="url(#lesion)"/>')
        elif i == 1:
            parts.append(f'<path d="{BLOB}" transform="translate({n(cx)} {cy})" fill="{t["mask_fg"]}"/>')
        else:
            parts.append(f'<path d="{BLOB}" transform="translate({n(cx)} {cy})" fill="url(#lesion)" opacity=".35"/>')
            parts.append(f'<path d="{BLOB}" transform="translate({n(cx)} {cy})" fill="none" stroke="{t["accent"]}" '
                         f'stroke-width="2.2" pathLength="100" stroke-dasharray="100" style="animation:trace 4.5s ease-in-out infinite"/>')
        parts.append(s.text(names[i], cx, y + ph + 17, 11, fill="muted", anchor="middle"))
        if i < 2:
            parts.append(s.text("→", x + pw + gap / 2, cy + 5, 15, "b", "accent", anchor="middle"))
    rise(s, .2, *parts, cls="fade")
    return s


# --------------------------------------------------------------------- vaani

# Sample exchanges from the demo reel on roydonsequeira.com, played with the
# site's timing: the question is typed, Vaani thinks, then the reply streams in.
VAANI_SCENES = [
    ("What has Roydon shipped?",
     "A WhatsApp agent that onboards customers from the very first message, Cortex, his own agent "
     "framework, and production medical AI at ReinHealth.ai."),
    ("We're hiring an AI agent engineer.",
     "Great, he’s open to full-time roles and contracts. What does the role involve, and what budget "
     "are you working with?"),
    ("Can you write my college essay?",
     "That’s outside what I do here. An agent that takes work like that off your team’s plate, though, "
     "is exactly what Roydon builds."),
]
# Seconds: typing starts, per typed character, thinking, per streamed character, hold.
ASK_START, ASK_CHAR, THINK, REPLY_CHAR, HOLD = .35, .032, 1.15, .015, 3.4

VAANI_CSS = (
    # A cover over text still to come; it shrinks towards its right edge.
    ".cv{transform-box:fill-box;transform-origin:right center;transform:scaleX(0)}"
    ".wv{transform-box:fill-box;transform-origin:center;animation:wv .9s ease-in-out infinite}"
    "@keyframes wv{0%,100%{transform:scaleY(.35)}50%{transform:scaleY(1)}}"
)


def mix(a: str, b: str, k: float) -> str:
    """The colour a share k of the way from a to b."""
    pa, pb = ([int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * k):02x}" for x, y in zip(pa, pb))


def reel(s: Svg, px: float, py: float, pw: float, ph: float) -> None:
    """A chat window that plays VAANI_SCENES on a loop. Every part is timed in
    one cycle and starts with a negative delay, so the loop is already running
    when the image loads and the first scene starts as the window fades in.
    With reduced motion the first exchange shows complete."""
    t = s.t
    s.css.append(VAANI_CSS)
    ix, ir = px + 20, px + pw - 20
    bubble, edge = mix(t["panel"], t["accent"], .14), mix(t["panel"], t["accent"], .42)
    parts = [f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="10" fill="{t["panel"]}" stroke="{t["line"]}"/>']
    hy = py + 24
    for j, bh in enumerate((5, 10, 15, 10, 5)):
        parts.append(f'<rect x="{n(ix + j * 4.6)}" y="{n(hy - bh / 2)}" width="2.4" height="{bh}" rx="1.2" '
                     f'fill="{t["accent"]}"/>')
    dot_x = ir - s.width("online", 10.5) - 10
    parts += [label(s, "VAANI", ix + 32, hy + 4, "ink", size=11),
              f'<circle class="ping" cx="{n(dot_x)}" cy="{hy}" r="3.5" fill="{t["accent"]}" opacity="0"/>',
              f'<circle cx="{n(dot_x)}" cy="{hy}" r="3.5" fill="{t["accent"]}"/>',
              s.text("online", ir, hy + 3.6, 10.5, fill="faint", anchor="end"),
              f'<rect x="{px + 1}" y="{py + 46}" width="{pw - 2}" height="1" fill="{t["line"]}"/>']
    gy = py + 72
    parts.append(s.text("Hi, I’m Vaani, Roydon’s personal AI assistant.", ix, gy, 14, "T"))
    sub = s.wrap("Ask me about his work, the agents he builds, or hiring him.", 13, ir - ix, "T")
    parts += [s.text(line, ix, gy + 19 + j * 18, 13, "T", "muted") for j, line in enumerate(sub)]
    by = gy + 19 + (len(sub) - 1) * 18 + 22  # the question bubble's top
    ry = by + 30 + 27                        # the first reply line's baseline

    scenes, clock = [], 0.0
    for ask, reply in VAANI_SCENES:
        a0 = clock + ASK_START
        a1 = a0 + len(ask) * ASK_CHAR
        r0 = a1 + THINK
        lines, spans, c = s.wrap(reply, 14, ir - ix, "T"), [], r0
        for line in lines:
            spans.append((c, c + len(line) * REPLY_CHAR))
            c += (len(line) + 1) * REPLY_CHAR
        scenes.append((clock, ask, a0, a1, r0, lines, spans, c + HOLD))
        clock = c + HOLD
    period = clock
    lag = n(s.t0 + .15 - period)

    def at(sec: float) -> str:
        return n(sec / period * 100)

    def run(name: str, frames: str) -> str:
        s.css.append(f"@keyframes {name}{{{frames}}}")
        return f"animation:{name} {n(period)}s linear {lag}s infinite"

    for k, (s0, ask, a0, a1, r0, lines, spans, end) in enumerate(scenes):
        qw = s.width(ask, 12.5)
        bx = ir - qw - 26
        tx = bx + 13
        out = [f'<rect x="{n(bx)}" y="{n(by)}" width="{n(qw + 26)}" height="30" rx="9" fill="{bubble}" '
               f'stroke="{edge}" style="{run(f"vb{k}", f"0%,{at(a0 - .12)}%{{opacity:0}}{at(a0)}%,100%{{opacity:1}}")}"/>',
               s.text(ask, tx, by + 19.5, 12.5),
               # Typed: the cover steps back one character at a time and the caret rides its edge.
               f'<rect class="cv" x="{n(tx)}" y="{n(by + 5)}" width="{n(qw)}" height="20" fill="{bubble}" style="'
               + run(f"vq{k}", f"0%,{at(a0)}%{{transform:scaleX(1);animation-timing-function:steps({len(ask)},end)}}"
                               f"{at(a1)}%,100%{{transform:scaleX(0)}}") + '"/>',
               f'<rect x="{n(tx)}" y="{n(by + 8)}" width="1.5" height="14" fill="{t["accent"]}" opacity="0" style="'
               + run(f"vc{k}", f"0%,{at(a0 - .02)}%{{opacity:0;transform:translateX(0)}}"
                               f"{at(a0)}%{{opacity:1;transform:translateX(0);animation-timing-function:steps({len(ask)},end)}}"
                               f"{at(a1)}%,{at(r0)}%{{opacity:1;transform:translateX({n(qw)}px)}}"
                               f"{at(r0 + .02)}%,100%{{opacity:0;transform:translateX({n(qw)}px)}}") + '"/>']
        # Streamed: each line's cover slides off at the reply's reading pace.
        for j, (line, (c0, c1)) in enumerate(zip(lines, spans)):
            y = ry + j * 20
            out += [s.text(line, ix, y, 14, "T"),
                    f'<rect class="cv" x="{n(ix - 1)}" y="{n(y - 14.5)}" width="{n(s.width(line, 14, "T") + 3)}" '
                    f'height="20" fill="{t["panel"]}" style="'
                    + run(f"vr{k}{j}", f"0%,{at(c0)}%{{transform:scaleX(1)}}{at(c1)}%,100%{{transform:scaleX(0)}}") + '"/>']
        bars = "".join(f'<rect class="wv" x="{n(ix + j * 4.6)}" y="{n(ry - 12)}" width="2.4" height="12" rx="1.2" '
                       f'fill="{t["accent"]}" style="animation-delay:{n(j * .11)}s"/>' for j in range(5))
        out.append(f'<g opacity="0" style="'
                   + run(f"vt{k}", f"0%,{at(a1 + .1)}%{{opacity:0}}{at(a1 + .3)}%,{at(r0 - .05)}%{{opacity:1}}"
                                   f"{at(r0 + .05)}%,100%{{opacity:0}}")
                   + f'">{bars}{s.text("thinking", ix + 32, ry - 2, 11, fill="faint")}</g>')
        shown = "0%{opacity:1}" if k == 0 else f"0%,{at(s0 - .02)}%{{opacity:0}}{at(s0)}%{{opacity:1}}"
        parts.append(f'<g opacity="{1 if k == 0 else 0}" style="'
                     + run(f"vs{k}", f"{shown}{at(end - .35)}%{{opacity:1}}{at(end)}%,100%{{opacity:0}}")
                     + f'">{"".join(out)}</g>')

    fy = py + ph - 14
    parts.append(s.text("SAMPLE EXCHANGES FROM THE SITE", ix, fy, 10, fill="faint", ls=.6))
    on, off = t["accent"], t["line"]
    for k, (s0, *_, end) in enumerate(scenes):
        frames = (f"0%,{at(end - .02)}%{{fill:{on}}}{at(end)}%,100%{{fill:{off}}}" if k == 0 else
                  f"0%,{at(s0 - .02)}%{{fill:{off}}}{at(s0)}%,{at(end - .02)}%{{fill:{on}}}{at(end)}%,100%{{fill:{off}}}")
        parts.append(f'<circle cx="{n(ir - 3 - (len(scenes) - 1 - k) * 12)}" cy="{n(fy - 3.5)}" r="3" '
                     f'fill="{on if k == 0 else off}" style="{run(f"vd{k}", frames)}"/>')
    rise(s, .15, *parts, cls="fade")


def vaani_card(fonts: Fonts, theme: str) -> Svg:
    ask0, reply0 = VAANI_SCENES[0]
    s = Svg(fonts, THEMES[theme], 1000, 344, "Vaani, the AI assistant on roydonsequeira.com",
            "Vaani answers visitors' questions about my work on roydonsequeira.com. Its system prompt is built "
            "from the site's portfolio data, and the API key and prompt stay on the server. A sample exchange "
            f"from the site: asked \"{ask0}\", it answers: {reply0}")
    s.t0 = T_VAANI
    paper(s, "surface", rx=16)
    x0 = 32
    rise(s, 0, label(s, "AI AGENT · LIVE ON MY SITE", x0, 44, size=11.5),
         s.text("Vaani", x0 - 2, 104, 56, "Di"),
         s.text("Kannada and Sanskrit for “voice”", x0 + s.width("Vaani", 56, "Di") + 14, 102, 15, "T", "muted"))
    lines = s.wrap("The assistant on my portfolio site. Visitors ask it about my work, my projects or a role "
                   "they’re hiring for.", 16, 480)
    rise(s, .1, *[s.text(line, x0, 140 + j * 23, 16, "T", "muted") for j, line in enumerate(lines)])
    feats = ["system prompt built from the site’s portfolio data",
             "API key and prompt stay server-side; the browser gets the stream",
             "30 requests per 10 minutes per visitor, keyed by a hashed IP",
             "replies in Hindi or Kannada when a visitor writes in them"]
    fy = 140 + len(lines) * 23 + 10
    for j, f in enumerate(feats):
        rise(s, .2 + j * .06, s.text("▸", x0, fy + j * 22, 13.5, fill="accent"), s.text(f, x0 + 18, fy + j * 22, 13))
    chips(s, ["Next.js", "TypeScript", "PHP", "OpenRouter"], x0, 300, delay=.3)
    rise(s, .35, s.text("Talk to Vaani at roydonsequeira.com →", 968, 317, 12, fill="accent", anchor="end"))
    reel(s, 560, 26, 408, 266)
    return s


# ---------------------------------------------------------------------- main

CARDS = {
    "masthead": masthead,
    "impact": impact,
    "upstream": upstream,
    "vaani": vaani_card,
    "cortex": cortex_card,
    "ragchatbot": rag_card,
    "soap": soap_card,
    "lesion": lesion_card,
}


def main(names: list[str]) -> None:
    unknown = set(names) - set(CARDS)
    if unknown:
        raise SystemExit(f"unknown card(s): {', '.join(sorted(unknown))}; choose from {', '.join(CARDS)}")
    fonts = Fonts()
    OUT.mkdir(exist_ok=True)
    today = date.today()
    data = merged_upstream() if not names or "upstream" in names else None
    drawn: set[tuple[str, str]] = set()
    for name in names or CARDS:
        build = CARDS[name]
        for theme in THEMES:
            card = build(fonts, theme, data, today) if name == "upstream" else build(fonts, theme)
            if name == "upstream":
                drawn |= card.used
            svg = card.render()
            path = OUT / f"{name}-{theme}.svg"
            path.write_text(svg, encoding="utf-8")
            print(f"{path.relative_to(ROOT)}  {len(svg) / 1024:.1f} KB")
    if data:
        write_upstream_block(data, today)
        print("README.md upstream block updated")
        if fonts.from_files():
            write_glyphs(fonts, drawn)
            print(f"{GLYPHS.relative_to(ROOT)} updated")


if __name__ == "__main__":
    main(sys.argv[1:])
