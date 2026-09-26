#!/usr/bin/env python3
"""Build the animated SVG artwork for the profile README (assets/*.svg).

Every string is drawn from Cascadia Code glyph outlines (SIL OFL 1.1) that are
embedded once per file and reused with <use>, so the art looks identical on
every OS and needs no web fonts. GitHub serves README images from a sandbox
that would block them anyway.

    pip install fonttools
    python scripts/build_assets.py

Set CASCADIA_FONT to a CascadiaCode.ttf path when not on Windows
(https://github.com/microsoft/cascadia-code/releases).
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
FONT = os.environ.get("CASCADIA_FONT", "C:/Windows/Fonts/CascadiaCode.ttf")

UPM = 2048
ADV = 1200  # Cascadia is monospaced: every glyph advances 1200 units

# Palette mirrors roydonsequeira.com: near-black canvas, terminal-mint signal,
# and the site's warm "paper" surface for the light variant.
THEMES = {
    "dark": dict(
        bg="#0a0b0d", surface="#101216", panel="#0d0f13", graphite="#171a20",
        line="#242931", grid="#ffffff", grid_op=0.035, ink="#edeff2",
        muted="#8b93a0", faint="#5c636e", accent="#00e6c3", soft="#6df3de",
        glow=0.16, mask_bg="#000000", mask_fg="#ffffff",
        dots=("#ff5f57", "#febc2e", "#28c840"),
        palette=("#171a20", "#ff5f57", "#28c840", "#febc2e", "#5ea1ff", "#c792ea", "#00e6c3", "#edeff2"),
    ),
    "light": dict(
        bg="#f6f5f1", surface="#ffffff", panel="#f1efea", graphite="#e9e6df",
        line="#dcd8cf", grid="#121417", grid_op=0.05, ink="#121417",
        muted="#555a63", faint="#7c8089", accent="#00735f", soft="#00b39a",
        glow=0.12, mask_bg="#000000", mask_fg="#ffffff",
        dots=("#ff5f57", "#febc2e", "#28c840"),
        palette=("#e9e6df", "#e5484d", "#2f9e44", "#e8a317", "#3b82f6", "#9b5de5", "#00735f", "#121417"),
    ),
}

BASE_CSS = (
    ".in{animation:rise .8s cubic-bezier(.23,1,.32,1) both}"
    "@keyframes rise{from{opacity:0;transform:translateY(10px)}}"
    ".fade{animation:fade .7s ease-out both}"
    "@keyframes fade{from{opacity:0}}"
    ".blink{animation:blink 1.05s steps(1,end) infinite}"
    "@keyframes blink{50%{opacity:0}}"
    ".spin{transform-box:fill-box;transform-origin:center;animation:spin 48s linear infinite}"
    "@keyframes spin{to{transform:rotate(360deg)}}"
    ".ping{transform-box:fill-box;transform-origin:center;animation:ping 2.2s cubic-bezier(0,0,.2,1) infinite}"
    "@keyframes ping{from{transform:scale(1);opacity:.75}to{transform:scale(3.2);opacity:0}}"
    ".grow{transform-box:fill-box;transform-origin:left center;animation:grow 1.1s cubic-bezier(.23,1,.32,1) both}"
    "@keyframes grow{from{transform:scaleX(0)}}"
    ".pop{transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.34,1.56,.64,1) both}"
    "@keyframes pop{from{opacity:0;transform:scale(.3)}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
)


def n(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def adv(size: float) -> float:
    return size * ADV / UPM


def tw(s: str, size: float, ls: float = 0) -> float:
    return len(s) * adv(size) + max(len(s) - 1, 0) * ls


def wrap(s: str, size: float, width: float) -> list[str]:
    limit = int(width // adv(size))
    lines, cur = [], ""
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > limit:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    return lines + [cur] if cur else lines


class Face:
    """Static instances of the Cascadia Code variable font, keyed r/m/b."""

    def __init__(self, path: str):
        self.fonts = {
            key: instancer.instantiateVariableFont(TTFont(path), {"wght": wght})
            for key, wght in (("r", 400), ("m", 600), ("b", 700))
        }
        self.cache: dict[tuple[str, str], str] = {}

    def outline(self, weight: str, ch: str) -> str:
        key = (weight, ch)
        if key not in self.cache:
            font = self.fonts[weight]
            name = font.getBestCmap().get(ord(ch))
            if name is None:
                raise SystemExit(f"Cascadia Code has no glyph for {ch!r}")
            glyphs = font.getGlyphSet()
            pen = SVGPathPen(glyphs, ntos=lambda v: str(round(v)))
            glyphs[name].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
            self.cache[key] = pen.getCommands()
        return self.cache[key]


class Svg:
    def __init__(self, face: Face, theme: dict, w: int, h: int, title: str, desc: str):
        self.face, self.t, self.w, self.h = face, theme, w, h
        self.title, self.desc = title, desc
        self.body: list[str] = []
        self.defs: list[str] = []
        self.css: list[str] = [BASE_CSS]
        self.glyphs: set[tuple[str, str]] = set()
        self._ids = 0

    def c(self, color: str) -> str:
        return self.t.get(color, color)

    def uid(self, prefix: str) -> str:
        self._ids += 1
        return f"{prefix}{self._ids}"

    def add(self, *parts: str) -> None:
        self.body.extend(parts)

    def text(self, s: str, x: float, y: float, size: float, w: str = "r", fill: str = "ink",
             anchor: str = "start", ls: float = 0, cls: str = "", op: float | None = None) -> str:
        """Glyph-outline text. `cls` may animate fill/opacity but never transform,
        because the group's transform attribute places the glyphs."""
        scale = size / UPM
        step = ADV + ls / scale
        width = tw(s, size, ls)
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
        uses = []
        for i, ch in enumerate(s):
            if ch == " ":
                continue
            self.glyphs.add((w, ch))
            uses.append(f'<use href="#{w}{ord(ch):x}" x="{round(i * step)}"/>')
        attrs = f' class="{cls}"' if cls else ""
        if op is not None:
            attrs += f' opacity="{n(op)}"'
        return (f'<g{attrs} fill="{self.c(fill)}" transform="translate({n(x)} {n(y)}) '
                f'scale({scale:.6f})">{"".join(uses)}</g>')

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
            f'<path id="{w}{ord(ch):x}" d="{self.face.outline(w, ch)}"/>' for w, ch in sorted(self.glyphs)
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="title desc">'
            f'<title id="title">{escape(self.title)}</title><desc id="desc">{escape(self.desc)}</desc>'
            f'<style>{"".join(self.css)}</style>'
            f'<defs>{"".join(self.defs)}{glyph_defs}</defs>{"".join(self.body)}</svg>'
        )


# ---------------------------------------------------------------- shared bits

def backdrop(s: Svg, rx: float = 20, glow: tuple[float, float, float] | None = None) -> None:
    t = s.t
    s.defs.append(f'<clipPath id="frame"><rect width="{s.w}" height="{s.h}" rx="{rx}"/></clipPath>')
    s.defs.append(
        f'<pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">'
        f'<path d="M28 0H0V28" fill="none" stroke="{t["grid"]}" stroke-opacity="{t["grid_op"]}"/></pattern>'
    )
    layers = f'<rect width="{s.w}" height="{s.h}" fill="{t["bg"]}"/><rect width="{s.w}" height="{s.h}" fill="url(#grid)"/>'
    if glow:
        gx, gy, gr = glow
        s.defs.append(
            f'<radialGradient id="glow" cx="{n(gx)}" cy="{n(gy)}" r="{n(gr)}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{t["accent"]}" stop-opacity="{t["glow"]}"/>'
            f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></radialGradient>'
        )
        layers += f'<rect width="{s.w}" height="{s.h}" fill="url(#glow)"/>'
    s.add(f'<g clip-path="url(#frame)">{layers}</g>',
          f'<rect x=".5" y=".5" width="{s.w - 1}" height="{s.h - 1}" rx="{rx - .5}" fill="none" stroke="{t["line"]}"/>')


def card_frame(s: Svg, glow_at: tuple[float, float] = (0, 0)) -> None:
    t = s.t
    s.defs.append(
        f'<radialGradient id="cglow" cx="{n(glow_at[0])}" cy="{n(glow_at[1])}" r="{n(s.w * .7)}" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{t["accent"]}" stop-opacity="{t["glow"] * .55}"/>'
        f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></radialGradient>'
    )
    s.add(f'<rect x=".5" y=".5" width="{s.w - 1}" height="{s.h - 1}" rx="15.5" fill="{t["surface"]}" stroke="{t["line"]}"/>',
          f'<rect x=".5" y=".5" width="{s.w - 1}" height="{s.h - 1}" rx="15.5" fill="url(#cglow)"/>')


def chips(s: Svg, items: list[str], x: float, y: float, size: float = 11.5) -> float:
    t = s.t
    h, pad = 24, 9
    out = []
    for item in items:
        w = tw(item, size) + pad * 2
        out.append(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{h}" rx="12" fill="{t["graphite"]}" stroke="{t["line"]}"/>')
        out.append(s.text(item, x + pad, y + 16.2, size, fill="muted"))
        x += w + 8
    s.add(*out)
    return x - 8


def box(s: Svg, x: float, y: float, w: float, h: float, label: str, sub: str = "",
        hl: bool = False, size: float = 11.5, cls: str = "", dashed: bool = False) -> str:
    t = s.t
    stroke = t["accent"] if hl else t["line"]
    dash = ' stroke-dasharray="4 4"' if dashed else ""
    klass = f' class="{cls}"' if cls else ""
    parts = [f'<rect{klass} x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="8" '
             f'fill="{t["panel"]}" stroke="{stroke}"{dash}/>']
    cx = x + w / 2
    if sub:
        parts.append(s.text(label, cx, y + h / 2 - 2, size, w="b", fill="accent" if hl else "ink", anchor="middle"))
        parts.append(s.text(sub, cx, y + h / 2 + 12, 10, fill="muted", anchor="middle"))
    else:
        parts.append(s.text(label, cx, y + h / 2 + size * .36, size, w="b", fill="accent" if hl else "ink", anchor="middle"))
    return "".join(parts)


def rise(s: Svg, delay: float, *parts: str, cls: str = "in") -> None:
    s.add(f'<g class="{cls}" style="animation-delay:{n(delay)}s">{"".join(parts)}</g>')


# ---------------------------------------------------------------------- hero

PHRASES = [
    "local-first agents that never phone home",
    "multi-agent systems with real guardrails",
    "RAG pipelines grounded in your own data",
    "healthcare AI that escalates when it should",
]


def hero(face: Face, theme: str) -> Svg:
    s = Svg(face, THEMES[theme], 1000, 400,
            "Roydon Sequeira — GenAI Engineer and AI Agent Architect",
            "I build AI agents that plan, retrieve and act, and know when to hand off to a human. "
            "AI Agent Developer at Code Crew Studio, based in Udupi, India.")
    t = s.t
    cx, cy, orbit = 800, 214, 128
    backdrop(s, glow=(cx, cy, 340))

    rise(s, 0.0, s.text("~/roydonsequeira", 44, 54, 13, fill="faint"),
         s.text("UDUPI, IN · UTC+05:30", 956, 54, 12, fill="faint", anchor="end", ls=1.2))
    rise(s, 0.1, s.text("Roydon Sequeira", 44, 146, 56, w="b"))
    rise(s, 0.22, s.text("GenAI Engineer · AI Agent Architect", 44, 190, 20, w="m", fill="accent"))
    rise(s, 0.34, s.text("I build AI agents that plan, retrieve and act,", 44, 232, 15, fill="muted"),
         s.text("and know when to hand off to a human.", 44, 256, 15, fill="muted"))

    # Prompt pill with a typewriter cycling through what I'm building.
    px, py, size = 62, 309, 15
    a = adv(size)
    s.defs.append(f'<clipPath id="typing"><rect x="{px - 4}" y="{py - 20}" width="{556 - 14 - px + 4}" height="28"/></clipPath>')
    pill = [f'<rect x="44" y="282" width="512" height="44" rx="10" fill="{t["panel"]}" stroke="{t["line"]}"/>',
            s.text("$", px, py, size, w="b", fill="accent"),
            s.text("building", px + 2 * a, py, size, fill="muted")]
    start = px + 11 * a
    period, per = 16.0, 16.0 / len(PHRASES)
    vis = per / period * 100
    s.css.append(f"@keyframes ph{{0%,{n(vis - .05)}%{{opacity:1}}{n(vis)}%,100%{{opacity:0}}}}")
    typed = []
    for i, phrase in enumerate(PHRASES):
        k, width = len(phrase), len(phrase) * a
        typing = min(0.045 * k, 1.9)
        p_a, p_b, p_c = typing / period * 100, (per - 0.9) / period * 100, (per - 0.35) / period * 100
        s.css.append(
            f"@keyframes ty{i}{{0%{{transform:translateX(0);animation-timing-function:steps({k},end)}}"
            f"{n(p_a)}%,{n(p_b)}%{{transform:translateX({n(width)}px);animation-timing-function:steps({k},end)}}"
            f"{n(p_c)}%,100%{{transform:translateX(0)}}}}"
        )
        delay = 0 if i == 0 else -(period - i * per)
        anim = f"{n(period)}s linear {n(delay)}s infinite"
        typed.append(
            f'<g style="opacity:{1 if i == 0 else 0};animation:ph {anim}">'
            + s.text(phrase, start, py, size, fill="ink")
            + f'<g style="transform:translateX({n(width)}px);animation:ty{i} {anim}">'
            f'<rect x="{n(start)}" y="{py - 19}" width="{n(40 * a + 60)}" height="26" fill="{t["panel"]}"/>'
            f'<rect class="blink" x="{n(start)}" y="{py - 14}" width="{n(a)}" height="18" fill="{t["accent"]}"/></g></g>'
        )
    rise(s, 0.46, *pill, f'<g clip-path="url(#typing)">{"".join(typed)}</g>')

    rise(s, 0.58,
         f'<circle class="ping" cx="52" cy="358" r="4.5" fill="{t["accent"]}" opacity="0"/>',
         f'<circle cx="52" cy="358" r="4.5" fill="{t["accent"]}"/>',
         s.text("AI Agent Developer @ Code Crew Studio · open to roles & contracts", 66, 362.5, 13, fill="muted"))

    # Agent graph: an orchestrator dispatching to the parts of an agent.
    nodes = [("PLAN", -90), ("MEMORY", -30), ("TOOLS", 30), ("GUARD", 90), ("RAG", 150), ("LLM", 210)]
    graph = [f'<circle cx="{cx}" cy="{cy}" r="{orbit}" fill="none" stroke="{t["line"]}" stroke-dasharray="2 6"/>',
             f'<circle class="spin" cx="{cx}" cy="{cy}" r="66" fill="none" stroke="{t["accent"]}" stroke-opacity=".45" stroke-dasharray="1 7 16 7"/>']
    boxes = []
    period = 3.6
    for i, (label, deg) in enumerate(nodes):
        r = math.radians(deg)
        nx, ny = cx + orbit * math.cos(r), cy + orbit * math.sin(r)
        ux, uy = math.cos(r), math.sin(r)
        x1, y1 = cx + ux * 40, cy + uy * 30
        x2, y2 = nx - ux * 22, ny - uy * 18
        length = math.hypot(x2 - x1, y2 - y1)
        out_d = f"M{n(x1)} {n(y1)}L{n(x2)} {n(y2)}"
        back_d = f"M{n(x2)} {n(y2)}L{n(x1)} {n(y1)}"
        delay = i * period / len(nodes)
        graph.append(f'<path d="{out_d}" stroke="{t["faint"]}" stroke-opacity=".55" stroke-width="1.2"/>')
        graph.append(s.pulse(out_d, length, period, delay, dash=16, width=2.8, travel=.42))
        graph.append(s.pulse(back_d, length, period, delay + period * .5, color="soft", width=1.6, dash=8, travel=.42))
        bw = 96
        s.css.append(
            f"@keyframes nf{i}{{0%,36%{{stroke:{t['line']}}}44%{{stroke:{t['accent']}}}70%,100%{{stroke:{t['line']}}}}}"
        )
        boxes.append(
            f'<rect x="{n(nx - bw / 2)}" y="{n(ny - 15)}" width="{bw}" height="30" rx="8" fill="{t["panel"]}" '
            f'stroke="{t["line"]}" style="animation:nf{i} {n(period)}s linear {n(delay)}s infinite"/>'
            + s.text(label, nx, ny + 4.2, 11.5, w="b", anchor="middle", ls=1)
        )
    center = [f'<rect x="{cx - 70}" y="{cy - 22}" width="140" height="44" rx="11" fill="{t["panel"]}" stroke="{t["accent"]}"/>',
              s.text("ORCHESTRATOR", cx, cy + 4.5, 12.5, w="b", fill="accent", anchor="middle", ls=.6)]
    rise(s, 0.3, *graph, *boxes, *center, cls="fade")
    return s


# ------------------------------------------------------------------ terminal

PIXELS = {
    "R": ["1111.", "1...1", "1...1", "1111.", "1.1..", "1..1.", "1...1"],
    "S": [".1111", "1....", "1....", ".111.", "....1", "....1", "1111."],
}

NEOFETCH = [
    ("Role", "AI Agent Developer @ Code Crew Studio"),
    ("Previous", "GenAI Engineer @ ReinHealth (stealth AI health)"),
    ("Focus", "Multi-agent systems, LLM orchestration, RAG"),
    ("Stack", "Python, LangChain, Qdrant, FastAPI, Docker"),
    ("Runtime", "Ollama for local-first, private inference"),
    ("Patterns", "ReAct · LATS · supervisor-worker · RAG"),
    ("Uptime", "2+ years shipping production AI"),
    ("Location", "Udupi, Karnataka, India"),
    ("Status", "● Open to AI engineering roles & contracts"),
]


def terminal(face: Face, theme: str) -> Svg:
    W = 880
    s = Svg(face, THEMES[theme], W, 470, "whoami",
            "Roydon Sequeira. " + ". ".join(f"{k}: {v.lstrip('● ')}" for k, v in NEOFETCH) + ".")
    t = s.t
    s.add(f'<rect x=".5" y=".5" width="{W - 1}" height="469" rx="15.5" fill="{t["surface"]}" stroke="{t["line"]}"/>',
          f'<path d="M.5 44V16A15.5 15.5 0 0 1 16 .5H{W - 16}A15.5 15.5 0 0 1 {W - .5} 16V44Z" fill="{t["panel"]}"/>',
          f'<path d="M.5 44.5H{W - .5}" stroke="{t["line"]}"/>')
    for i, color in enumerate(t["dots"]):
        s.add(f'<circle cx="{26 + i * 20}" cy="22" r="6" fill="{color}"/>')
    s.add(s.text("roy@cortex — zsh — 100×28", W / 2, 26.5, 12.5, fill="faint", anchor="middle"))

    size, a, x0 = 15, adv(15), 32
    prompt, cmd = "roy@cortex:~$ ", "neofetch --user roydon"
    y = 84
    cx = x0 + len(prompt) * a
    width = len(cmd) * a
    s.css.append(f"@keyframes cmd{{from{{transform:translateX(0)}}to{{transform:translateX({n(width)}px)}}}}"
                 "@keyframes gone{0%,97%{opacity:1}100%{opacity:0}}")
    s.add(s.text("roy@cortex", x0, y, size, w="b", fill="accent"), s.text(":~$", x0 + 10 * a, y, size, fill="ink"),
          s.text(cmd, cx, y, size),
          f'<g style="transform:translateX({n(width)}px);animation:cmd 1s steps({len(cmd)},end) .35s both">'
          f'<rect x="{n(cx)}" y="{y - 18}" width="{n(width + 20)}" height="26" fill="{t["surface"]}"/>'
          f'<rect x="{n(cx)}" y="{y - 14}" width="{n(a)}" height="18" fill="{t["accent"]}" '
          f'style="opacity:0;animation:gone 1.45s linear both"/></g>')

    # Pixel monogram.
    px, top, cell = 58, 150, 17
    s.defs.append(f'<linearGradient id="mono" x1="0" y1="{top}" x2="0" y2="{top + 7 * cell}" gradientUnits="userSpaceOnUse">'
                  f'<stop offset="0" stop-color="{t["soft"]}"/><stop offset="1" stop-color="{t["accent"]}"/></linearGradient>')
    pixels = []
    for li, letter in enumerate("RS"):
        for r, row in enumerate(PIXELS[letter]):
            for c, on in enumerate(row):
                if on != "1":
                    continue
                col = li * 6 + c
                pixels.append(f'<rect class="pop" x="{px + col * cell}" y="{top + r * cell}" width="{cell - 2}" '
                              f'height="{cell - 2}" rx="2" fill="url(#mono)" style="animation-delay:{n(1.45 + col * .04 + r * .02)}s"/>')
    s.add(*pixels)
    s.add(s.text("AGENTS · RAG · LLMOPS", px + (11 * cell - 2) / 2, top + 7 * cell + 34, 11, fill="faint", anchor="middle", ls=1.4))

    ix, iy, lh = 300, 126, 25
    head = "roydon@udupi"
    rise(s, 1.45, s.text("roydon", ix, iy, size, w="b", fill="accent"), s.text("@", ix + 6 * a, iy, size),
         s.text("udupi", ix + 7 * a, iy, size, w="b", fill="accent"),
         s.text("-" * len(head), ix, iy + lh, size, fill="faint"), cls="fade")
    for i, (key, value) in enumerate(NEOFETCH):
        yy = iy + (i + 2) * lh
        parts = [s.text(f"{key}:", ix, yy, size, w="b", fill="accent")]
        vx = ix + 10 * a
        if value.startswith("●"):
            parts.append(f'<circle class="ping" cx="{n(vx + a / 2)}" cy="{yy - 5}" r="4" fill="{t["accent"]}" opacity="0"/>')
            parts.append(f'<circle cx="{n(vx + a / 2)}" cy="{yy - 5}" r="4" fill="{t["accent"]}"/>')
            parts.append(s.text(value[2:], vx + 2 * a, yy, size, fill="ink"))
        else:
            parts.append(s.text(value, vx, yy, size, fill="ink"))
        rise(s, 1.55 + i * .07, *parts)

    py = iy + (len(NEOFETCH) + 2) * lh - 4
    blocks = [f'<rect class="pop" x="{ix + i * 34}" y="{py}" width="30" height="16" rx="3" fill="{color}" '
              f'style="animation-delay:{n(2.25 + i * .05)}s"/>' for i, color in enumerate(t["palette"])]
    s.add(*blocks)

    fy = 446
    rise(s, 2.6, s.text("roy@cortex", x0, fy, size, w="b", fill="accent"), s.text(":~$", x0 + 10 * a, fy, size),
         f'<rect class="blink" x="{n(cx)}" y="{fy - 14}" width="{n(a)}" height="18" fill="{t["accent"]}"/>', cls="fade")
    return s


# -------------------------------------------------------------------- impact

IMPACT = [
    ("REINHEALTH · PROD", "~70%", "less manual patient-intake workload", "bar", .70),
    ("REINHEALTH · PROD", "<5 min", "patient intake, down from 15 min", "compare", 5 / 15),
    ("LOCAL LLM ORCHESTRATION", "0", "patient records sent to external APIs", "dots", 1),
    ("CORTEX · OPEN SOURCE", "391", "tests: 204 unit + 187 live conversations", "stack", 204 / 391),
]


def impact(face: Face, theme: str) -> Svg:
    s = Svg(face, THEMES[theme], 1000, 196, "Impact",
            "About 70% less manual patient-intake work. Patient intake down from 15 minutes to under 5. "
            "Zero patient records sent to external APIs. 391 tests behind CORTEX: 204 unit and 187 live conversations.")
    t = s.t
    tile_w, gap = 235, 20
    for i, (tag, num, caption, viz, frac) in enumerate(IMPACT):
        x = i * (tile_w + gap)
        ix, iw = x + 20, tile_w - 40
        s.add(f'<rect x="{x + .5}" y=".5" width="{tile_w - 1}" height="195" rx="13.5" fill="{t["surface"]}" stroke="{t["line"]}"/>')
        parts = [s.text(tag, ix, 32, 11, w="m", fill="accent", ls=.8),
                 s.text(num, ix, 86, 44, w="b")]
        for j, line in enumerate(wrap(caption, 14, iw)):
            parts.append(s.text(line, ix, 116 + j * 20, 14, fill="muted"))
        rise(s, .1 + i * .12, *parts)

        by, d = 170, .5 + i * .12
        if viz == "bar":
            s.add(f'<rect x="{ix}" y="{by}" width="{iw}" height="6" rx="3" fill="{t["graphite"]}"/>',
                  f'<rect class="grow" x="{ix}" y="{by}" width="{n(iw * frac)}" height="6" rx="3" fill="{t["accent"]}" style="animation-delay:{d}s"/>')
        elif viz == "compare":
            s.add(f'<rect class="grow" x="{ix}" y="{by - 5}" width="{iw}" height="5" rx="2.5" fill="{t["faint"]}" opacity=".6" style="animation-delay:{d}s"/>',
                  f'<rect class="grow" x="{ix}" y="{by + 4}" width="{n(iw * frac)}" height="5" rx="2.5" fill="{t["accent"]}" style="animation-delay:{d + .25}s"/>')
        elif viz == "dots":
            for k in range(14):
                s.add(f'<rect class="pop" x="{n(ix + k * iw / 14)}" y="{by - 2}" width="10" height="10" rx="2.5" '
                      f'fill="none" stroke="{t["accent"]}" style="animation-delay:{n(d + k * .04)}s"/>')
        elif viz == "stack":
            s.add(f'<rect x="{ix}" y="{by}" width="{iw}" height="6" rx="3" fill="{t["graphite"]}"/>',
                  f'<rect class="grow" x="{ix}" y="{by}" width="{iw}" height="6" rx="3" fill="{t["soft"]}" opacity=".55" style="animation-delay:{d}s"/>',
                  f'<rect class="grow" x="{ix}" y="{by}" width="{n(iw * frac)}" height="6" rx="3" fill="{t["accent"]}" style="animation-delay:{d + .2}s"/>')
    return s


# ------------------------------------------------------------------ projects

def cortex_card(face: Face, theme: str) -> Svg:
    s = Svg(face, THEMES[theme], 1000, 340, "CORTEX — Private Intelligence Framework",
            "A private AI agent that runs entirely on your own machine: planning, sandboxed tools, "
            "four-tier memory, streaming UI and OpenTelemetry tracing, powered by Ollama.")
    t = s.t
    card_frame(s, (1000, 0))
    x0 = 32
    rise(s, 0, s.text("FLAGSHIP · OPEN SOURCE · MIT", x0, 44, 11.5, w="m", fill="accent", ls=1.3),
         s.text("CORTEX", x0, 92, 40, w="b"),
         s.text("Private Intelligence Framework", x0 + tw("CORTEX", 40) + 16, 91, 16, fill="muted"))
    desc = ("A private AI agent that runs entirely on your own machine: it plans, uses sandboxed tools, "
            "remembers you across sessions and streams every step, on a 6 GB laptop GPU. No cloud, no API keys.")
    rise(s, .1, *[s.text(line, x0, 126 + j * 21, 14.5, fill="muted") for j, line in enumerate(wrap(desc, 14.5, 548))])
    feats = ["4-tier memory: working · episodic · semantic · procedural",
             "LATS tree search + supervisor-worker orchestration",
             "guardrails enforced in code, not prompts",
             "OpenTelemetry spans on every model, tool and memory call"]
    for j, f in enumerate(feats):
        rise(s, .2 + j * .06, s.text("▸", x0, 204 + j * 22, 13.5, fill="accent"), s.text(f, x0 + 18, 204 + j * 22, 13.5))
    chips(s, ["Python 3.12", "FastAPI", "Next.js", "ChromaDB", "Ollama", "OpenTelemetry"], x0, 298)
    s.add(s.text("roydonsequeira/CORTEX-Private-Intelligence-Framework →", 968, 316, 12, fill="accent", anchor="end"))

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
    arch = []
    for d, length, delay in edges:
        arch.append(f'<path d="{d}" fill="none" stroke="{t["line"]}" stroke-width="1.2"/>')
    arch.append(f'<path d="M676 236V262M784 236V262" fill="none" stroke="{t["line"]}" stroke-width="1.2" stroke-dasharray="3 4"/>')
    for d, length, delay in edges:
        arch.append(s.pulse(d, length, period, delay, dash=10, travel=.22))
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


def half_card(face: Face, theme: str, title: str, label: str, desc: str, stack: list[str], a11y: str) -> tuple[Svg, float]:
    s = Svg(face, THEMES[theme], 490, 300, title, a11y)
    card_frame(s, (490, 0))
    rise(s, 0, s.text(label, 28, 40, 11, w="m", fill="accent", ls=1.2),
         s.text("→", 462, 40, 14, w="b", fill="accent", anchor="end"),
         s.text(title, 28, 76, 25, w="b"))
    lines = wrap(desc, 14, 434)
    rise(s, .1, *[s.text(line, 28, 104 + j * 20, 14, fill="muted") for j, line in enumerate(lines)])
    chips(s, stack, 28, 258)
    return s, 104 + len(lines) * 20


def rag_card(face: Face, theme: str) -> Svg:
    s, _ = half_card(face, theme, "RagChatbot", "RAG · OPEN SOURCE",
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
        parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="30" rx="8" fill="{t["panel"]}" stroke="{t["line"]}" '
                     f'style="animation:rg{i} {period}s linear infinite"/>')
        parts.append(s.text(st, x + bw / 2, y + 19, 11, w="b", anchor="middle", fill="accent" if i == 4 else "ink"))
    parts.append(s.text("SSE token stream → answer grounded in your files", 28, 234, 11, fill="faint"))
    rise(s, .2, *parts, cls="fade")
    return s


def soap_card(face: Face, theme: str) -> Svg:
    s, _ = half_card(face, theme, "Clinical SOAP Notes", "HEALTHCARE · n8n · OPEN SOURCE",
                     "Text or voice in, structured SOAP note out. Three n8n workflows (TTT, STT, TTS) on a local LLM.",
                     ["n8n", "Ollama · Gemma 3", "ElevenLabs", "PostgreSQL"],
                     "n8n workflows that turn clinical text or voice into structured SOAP notes with a local LLM.")
    t = s.t
    words = ["subjective", "objective", "assessment", "plan"]
    tw_, gap, y = 96, 16, 158
    period = 4.8
    parts = []
    for i, (letter, word) in enumerate(zip("SOAP", words)):
        x = 28 + i * (tw_ + gap)
        on, hold = i * 12 + 4, 78
        s.css.append(f"@keyframes sp{i}{{0%,{on}%{{fill:{t['panel']};stroke:{t['line']}}}"
                     f"{on + 5}%,{hold}%{{fill:{t['accent']};stroke:{t['accent']}}}{hold + 8}%,100%{{fill:{t['panel']};stroke:{t['line']}}}}}"
                     f"@keyframes sl{i}{{0%,{on}%{{fill:{t['ink']}}}{on + 5}%,{hold}%{{fill:{t['bg']}}}{hold + 8}%,100%{{fill:{t['ink']}}}}}")
        parts.append(f'<rect x="{x}" y="{y}" width="{tw_}" height="54" rx="10" fill="{t["panel"]}" stroke="{t["line"]}" '
                     f'style="animation:sp{i} {period}s ease-in-out infinite"/>')
        parts.append(s.text(letter, x + tw_ / 2, y + 38, 30, w="b", anchor="middle", cls=f"sl{i}"))
        s.css.append(f".sl{i}{{animation:sl{i} {period}s ease-in-out infinite}}")
        parts.append(s.text(word, x + tw_ / 2, y + 74, 11, fill="muted", anchor="middle"))
    rise(s, .2, *parts, cls="fade")
    return s


BLOB = "M0 -24C14 -26 28 -14 26 0C25 14 12 26 -2 24C-16 22 -28 12 -26 -2C-24 -16 -13 -22 0 -24Z"


def lesion_card(face: Face, theme: str) -> Svg:
    s, _ = half_card(face, theme, "Skin Lesion Segmentation", "COMPUTER VISION · OPEN SOURCE",
                     "U-Net (PyTorch) vs ResU-Net (TensorFlow 2) on 2,594 ISIC 2018 dermoscopy images, with a Streamlit demo.",
                     ["PyTorch", "TensorFlow", "OpenCV", "Streamlit"],
                     "Skin lesion segmentation on ISIC 2018 using U-Net in PyTorch and ResU-Net in TensorFlow 2.")
    t = s.t
    pw, ph, y = 118, 66, 152
    gap = (434 - 3 * pw) / 2
    s.defs.append(f'<radialGradient id="lesion" cx=".45" cy=".45" r=".6"><stop offset="0" stop-color="{t["accent"]}" stop-opacity=".95"/>'
                  f'<stop offset="1" stop-color="{t["soft"]}" stop-opacity=".35"/></radialGradient>')
    s.css.append("@keyframes trace{0%{stroke-dashoffset:100}45%,85%{stroke-dashoffset:0}100%{stroke-dashoffset:-100}}")
    parts = []
    labels = ["dermoscopy", "predicted mask", "contour"]
    for i in range(3):
        x = 28 + i * (pw + gap)
        cx, cy = x + pw / 2, y + ph / 2
        fill = t["mask_bg"] if i == 1 else t["panel"]
        parts.append(f'<rect x="{n(x)}" y="{y}" width="{pw}" height="{ph}" rx="9" fill="{fill}" stroke="{t["line"]}"/>')
        if i == 0:
            parts.append(f'<path d="{BLOB}" transform="translate({n(cx)} {cy})" fill="url(#lesion)"/>')
        elif i == 1:
            parts.append(f'<path d="{BLOB}" transform="translate({n(cx)} {cy})" fill="{t["mask_fg"]}"/>')
        else:
            parts.append(f'<path d="{BLOB}" transform="translate({n(cx)} {cy})" fill="url(#lesion)" opacity=".35"/>')
            parts.append(f'<path d="{BLOB}" transform="translate({n(cx)} {cy})" fill="none" stroke="{t["accent"]}" '
                         f'stroke-width="2.2" pathLength="100" stroke-dasharray="100" style="animation:trace 4.5s ease-in-out infinite"/>')
        parts.append(s.text(labels[i], cx, y + ph + 17, 11, fill="muted", anchor="middle"))
        if i < 2:
            parts.append(s.text("→", x + pw + gap / 2, cy + 5, 15, w="b", fill="accent", anchor="middle"))
    rise(s, .2, *parts, cls="fade")
    return s


LAB = [
    ("NEXUS", "AI content intelligence SaaS"),
    ("Code Review Agent", "multi-agent PR reviews"),
    ("Resume Analyzer", "3 agents, <400 ms, 39 tests"),
    ("AI Proxy Agent", "WhatsApp, calendar, leads"),
    ("Research Agent", "search, retrieval, citations"),
]


def lab_card(face: Face, theme: str) -> Svg:
    s = Svg(face, THEMES[theme], 490, 300, "In the lab",
            "Private builds: " + "; ".join(f"{a}, {b}" for a, b in LAB) + ". More on roydonsequeira.com.")
    t = s.t
    card_frame(s, (490, 0))
    rise(s, 0, s.text("IN THE LAB · PRIVATE BUILDS", 28, 40, 11, w="m", fill="accent", ls=1.2),
         s.text("→", 462, 40, 14, w="b", fill="accent", anchor="end"),
         s.text("Shipping next", 28, 76, 25, w="b"))
    for i, (name, what) in enumerate(LAB):
        y = 114 + i * 27
        rise(s, .12 + i * .07,
             f'<rect x="28" y="{y - 11}" width="6" height="6" rx="1.5" fill="{t["accent"]}"/>',
             s.text(name, 44, y + .5, 13.5, w="b"),
             s.text(what, 44 + tw(name, 13.5) + 12, y + .5, 13, fill="muted"))
    s.add(f'<path d="M28 250.5H462" stroke="{t["line"]}"/>')
    s.add(s.text("private for now · more on roydonsequeira.com", 28, 278, 12, fill="muted"))
    return s


# ------------------------------------------------------------------ timeline

def timeline(face: Face, theme: str) -> Svg:
    s = Svg(face, THEMES[theme], 1000, 296, "Career timeline",
            "Machine Learning Intern at Igeeks Technologies, June to July 2023. GenAI Engineer at ReinHealth, "
            "July 2024 to February 2026. AI Agent Developer at Code Crew Studio since February 2026. "
            "B.E. in AI and Machine Learning at NMAM Institute of Technology, 2020 to 2024. Executive PG "
            "Certification in Data Science and AI, iHUB DivyaSampark IIT Roorkee, 2024 to 2026.")
    t = s.t
    x0, x1, y0, y1 = 170, 960, 2020.0, 2027.0

    def X(year: float) -> float:
        return x0 + (year - y0) / (y1 - y0) * (x1 - x0)

    s.add(f'<rect x=".5" y=".5" width="999" height="295" rx="15.5" fill="{t["surface"]}" stroke="{t["line"]}"/>')
    for yr in range(2020, 2027):
        s.add(f'<path d="M{n(X(yr))} 52V270" stroke="{t["line"]}" stroke-dasharray="2 5"/>',
              s.text(str(yr), X(yr), 40, 12.5, fill="faint", anchor="middle"))
    now = X(2026.74)
    s.css.append("@keyframes march{to{stroke-dashoffset:-14}}")
    s.add(f'<path d="M{n(now)} 50V270" stroke="{t["accent"]}" stroke-dasharray="4 3" style="animation:march 1.2s linear infinite"/>',
          s.text("NOW", now, 40, 12, w="b", fill="accent", anchor="middle", ls=1))
    s.add(s.text("WORK", 32, 134, 12, w="m", fill="faint", ls=2), s.text("LEARN", 32, 250, 12, w="m", fill="faint", ls=2))

    work = [
        (2023.42, 2023.58, "ML Intern · Igeeks Technologies", "Jun – Jul 2023 · Bengaluru", False),
        (2024.50, 2026.08, "GenAI Engineer · ReinHealth", "Jul 2024 – Feb 2026 · remote, US", False),
        (2026.08, 2026.74, "AI Agent Developer · Code Crew Studio", "Feb 2026 – now · remote", True),
    ]
    for i, (a, b, role, when, current) in enumerate(work):
        y = 64 + i * 52
        xa, xb = X(a), X(b)
        fill = t["accent"]
        parts = [f'<rect class="grow" x="{n(xa)}" y="{y}" width="{n(max(xb - xa, 8))}" height="24" rx="5" fill="{fill}" '
                 f'opacity="{1 if current else .55}" style="animation-delay:{n(.2 + i * .25)}s"/>']
        if current:
            parts.append(f'<path d="M{n(xb + 4)} {y + 12}H{x1}" stroke="{t["accent"]}" stroke-dasharray="3 4" opacity=".7"/>')
            parts.append(f'<circle class="ping" cx="{n(xb)}" cy="{y + 12}" r="5" fill="{t["accent"]}" opacity="0"/>')
        parts.append(s.text(role, xa - 12, y + 10, 14, w="m", anchor="end"))
        parts.append(s.text(when, xa - 12, y + 27, 12, fill="muted", anchor="end"))
        rise(s, .15 + i * .25, *parts, cls="fade")

    s.add(f'<path d="M150 222.5H968" stroke="{t["line"]}"/>')
    learn = [
        (2020.60, 2024.45, "B.E. AI & ML · NMAM Institute of Technology", 13),
        (2024.50, 2026.50, "PG · DS & AI · IIT Roorkee", 12),
    ]
    for i, (a, b, label, size) in enumerate(learn):
        xa, xb = X(a), X(b)
        rise(s, .9 + i * .25,
             f'<rect class="grow" x="{n(xa)}" y="234" width="{n(xb - xa)}" height="30" rx="6" fill="{t["graphite"]}" '
             f'stroke="{t["line"]}" style="animation-delay:{n(.9 + i * .25)}s"/>',
             s.text(label, xa + 12, 253.5, size, w="m"), cls="fade")
    return s


# -------------------------------------------------------------------- footer

def footer(face: Face, theme: str) -> Svg:
    s = Svg(face, THEMES[theme], 1000, 200, "Let's build agents that ship.",
            "Open to AI engineering roles, contracts and production agent builds.")
    t = s.t
    backdrop(s, glow=(500, 100, 420))
    head = "Let's build agents that ship."
    size = 34
    w = tw(head, size)
    rise(s, 0, s.text(head, 500, 94, size, w="b", anchor="middle"))
    s.defs.append(f'<linearGradient id="sweep" x1="0" x2="1"><stop offset="0" stop-color="{t["accent"]}" stop-opacity="0"/>'
                  f'<stop offset=".5" stop-color="{t["accent"]}"/><stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></linearGradient>')
    s.css.append(f"@keyframes sweep{{from{{transform:translateX({n(-w)}px)}}to{{transform:translateX({n(w)}px)}}}}")
    s.defs.append(f'<clipPath id="ul"><rect x="{n(500 - w / 2)}" y="108" width="{n(w)}" height="3"/></clipPath>')
    s.add(f'<rect x="{n(500 - w / 2)}" y="108" width="{n(w)}" height="3" rx="1.5" fill="{t["line"]}"/>',
          f'<g clip-path="url(#ul)"><rect x="{n(500 - w / 2)}" y="108" width="{n(w)}" height="3" fill="url(#sweep)" '
          f'style="animation:sweep 3.2s cubic-bezier(.77,0,.175,1) infinite"/></g>')
    rise(s, .15, s.text("AI engineering roles · contracts · production agent builds", 500, 146, 14, fill="muted", anchor="middle"))
    for side in (-1, 1):
        xs = [500 + side * (w / 2 + 30 + k * 36) for k in range(4)]
        xs = [x for x in xs if 24 < x < 976]
        d = f"M{n(xs[-1])} 88H{n(xs[0])}"
        s.add(f'<path d="{d}" stroke="{t["line"]}"/>',
              s.pulse(d, abs(xs[-1] - xs[0]), 2.6, 0 if side < 0 else 1.3, dash=14, travel=.6))
        for k, x in enumerate(xs):
            s.add(f'<circle cx="{n(x)}" cy="88" r="{4 if k == 0 else 3}" fill="{t["panel"]}" stroke="{t["accent"] if k == 0 else t["line"]}"/>')
    return s


ASSETS = {
    "hero": hero,
    "whoami": terminal,
    "impact": impact,
    "cortex": cortex_card,
    "ragchatbot": rag_card,
    "soap": soap_card,
    "lesion": lesion_card,
    "lab": lab_card,
    "timeline": timeline,
    "footer": footer,
}


def main() -> None:
    face = Face(FONT)
    OUT.mkdir(exist_ok=True)
    for name, build in ASSETS.items():
        for theme in THEMES:
            svg = build(face, theme).render()
            path = OUT / f"{name}-{theme}.svg"
            path.write_text(svg, encoding="utf-8")
            print(f"{path.relative_to(ROOT)}  {len(svg) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
