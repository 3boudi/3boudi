#!/usr/bin/env python3
"""
Render the 3boudi GitHub profile README's cards as animated SVGs into cards/.

Design: "Three Worlds" editorial paper-and-ink system (warm paper #f3f3f1, deep
ink #111111, Cobalt Blue #2f55ff, Vermilion Red #ef3b2d, Warm Gold #ffc81a;
Instrument Serif, Geist, Geist Mono).

Every card is a standalone SVG displayed through <img>, so it uses only what
GitHub allows inside sandboxed SVGs: inline CSS @keyframes, SMIL animations,
and subset WOFF fonts embedded as base64 data URIs (no JS, no external requests).

Live data comes from data/contributions.json and data/profile.json, refreshed
daily by .github/workflows/update-profile-art.yml.

Set STATIC=1 in the environment to render every card at its final frame for
headless-browser visual verification before pushing.
"""
import base64
import datetime
import json
import os
import re
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
CONTRIB_DATA = os.path.join(ROOT, "data", "contributions.json")
PROFILE_DATA = os.path.join(ROOT, "data", "profile.json")
OUT = os.path.join(ROOT, "cards")
FONTS = os.path.join(ROOT, "fonts")
PORTRAIT = os.path.join(ROOT, "assets", "portrait-ascii.svg")

# ---- brand tokens -----------------------------------------------------------
PAPER = "#f3f3f1"
PAPER_DEEP = "#e2e2de"
INK = "#111111"
INK_SOFT = "#3a3a3c"
MUTED = "#6e6e73"
RULE = "#dcdcd7"
TECH = "#2f55ff"     # Cobalt Blue
STUDIO = "#ef3b2d"   # Vermilion Red
LEARN = "#ffc81a"    # Warm Gold
W = 880              # Full card width matching GitHub's README column at 100%

SERIF = "'Instrument Serif', Georgia, serif"
SANS = "Geist, system-ui, -apple-system, sans-serif"
MONO = "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

FONT_FILES = {
    "serif": ("Instrument Serif", "normal", 400, "serif-400.woff"),
    "serif-i": ("Instrument Serif", "italic", 400, "serif-italic.woff"),
    "sans": ("Geist", "normal", 400, "geist-400.woff"),
    "sans-b": ("Geist", "normal", 600, "geist-600.woff"),
    "mono": ("Geist Mono", "normal", 400, "geistmono-400.woff"),
}

BASE_CSS = """
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes growx{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes pop{0%{opacity:0;transform:scale(.3)}70%{opacity:1;transform:scale(1.15)}100%{opacity:1;transform:none}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
@keyframes nudge{0%,100%{transform:none}50%{transform:translateX(4px)}}
@keyframes nudgeup{0%,100%{transform:none}50%{transform:translate(3px,-3px)}}
.r{opacity:0;animation:rise .8s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box}
.f{opacity:0;animation:fade .9s ease-out both}
.g{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow .8s cubic-bezier(.2,.7,.2,1) both}
.gx{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:growx .9s cubic-bezier(.2,.7,.2,1) both}
.p{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .4s ease-out both}
.live{animation:pulse 1.6s ease-in-out infinite}
.n{transform-box:fill-box;animation:nudge 1.8s ease-in-out infinite}
.nu{transform-box:fill-box;animation:nudgeup 1.8s ease-in-out infinite}
@keyframes tilein{0%{opacity:0;transform:translateY(90px) scale(.6) rotate(-9deg)}55%{opacity:1;transform:translateY(-10px) scale(1.05) rotate(2deg)}75%{transform:translateY(3px) scale(.98) rotate(-.8deg)}90%{transform:translateY(-1px) scale(1.01) rotate(.2deg)}100%{opacity:1;transform:none}}
@keyframes slidein{from{opacity:0;transform:translateX(-26px)}to{opacity:1;transform:none}}
@keyframes arrowin{0%{opacity:0;transform:translateX(-30px)}60%{opacity:1;transform:translateX(6px)}100%{opacity:1;transform:none}}
@keyframes roll{from{transform:translateY(60px)}to{transform:none}}
@keyframes sheen{0%{transform:translateX(-260px) skewX(-20deg)}22%,100%{transform:translateX(420px) skewX(-20deg)}}
@keyframes ring{0%{opacity:.7;transform:scale(.2)}100%{opacity:0;transform:scale(2.4)}}
.ti{opacity:0;transform-box:fill-box;transform-origin:50% 60%;animation:tilein 1.1s cubic-bezier(.2,.8,.2,1) both}
.sl{opacity:0;transform-box:fill-box;animation:slidein .6s cubic-bezier(.2,.7,.2,1) both}
.ai{opacity:0;transform-box:fill-box;animation:arrowin .7s cubic-bezier(.2,.7,.2,1) both}
.ro{transform-box:fill-box;animation:roll .8s cubic-bezier(.15,.8,.2,1) both}
.sh{animation:sheen 5s ease-in-out infinite}
.rg{opacity:0;transform-box:fill-box;transform-origin:center;animation:ring 1s ease-out both}
@media (prefers-reduced-motion: reduce){.r,.f,.g,.gx,.p,.live,.n,.nu,.ti,.sl,.ai,.ro,.rg{animation:none!important;opacity:1!important;transform:none!important}.sh,.rg{display:none}}
"""

_FONT_CACHE = {}


def font_face(keys):
    out = []
    for k in keys:
        if k not in _FONT_CACHE:
            fam, style, weight, fn = FONT_FILES[k]
            with open(os.path.join(FONTS, fn), "rb") as fp:
                b64 = base64.b64encode(fp.read()).decode("ascii")
            _FONT_CACHE[k] = (
                f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{weight};"
                f"src:url(data:font/woff;base64,{b64}) format('woff')}}"
            )
        out.append(_FONT_CACHE[k])
    return "".join(out)


GAP = 12       # horizontal gap between 3-up cards, baked into SVG transparent padding
BOTTOM = 12    # bottom padding per row, matching GAP


def svg(w, h, body, fonts, label, extra_css="", left=0, right=0, bottom=BOTTOM):
    """Wrap card body (w x h) in a transparent canvas padded so 3-column rows align cleanly."""
    if left:
        body = f'<g transform="translate({left:.3f} 0)">{body}</g>'
    total_w, total_h = w + left + right, h + bottom
    css = font_face(fonts) + BASE_CSS + extra_css
    if os.environ.get("STATIC"):
        css += (
            ".r,.f,.g,.gx,.p,.live,.n,.nu,.ti,.sl,.ai,.ro"
            "{animation:none!important;opacity:1!important;transform:none!important}"
            ".sh,.rg{display:none}"
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.3f}" height="{total_h}" '
        f'viewBox="0 0 {total_w:.3f} {total_h}" role="img" aria-label="{escape(label)}">'
        f"<title>{escape(label)}</title>"
        f"<style>{css}</style>{body}</svg>"
    )


def write(name, content):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"wrote cards/{name:36s} ({len(content) // 1024:3d} KB)")


def d(s):
    return f'style="animation-delay:{s:.2f}s"'


def wrap(text, n):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > n:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line] if line else lines


def text_lines(x, y, lines, lh, attrs):
    return "".join(
        f'<text x="{x}" y="{y + i * lh}" {attrs}>{escape(line)}</text>'
        for i, line in enumerate(lines)
    )


# ---- 1 · hero ---------------------------------------------------------------
def hero():
    h = 420
    with open(PORTRAIT, encoding="utf-8") as fp:
        src = fp.read()
    rows = re.findall(
        r'<text xml:space="preserve"[^>]*\by="([\d.]+)"[^>]*\bfont-size="([\d.]+)"[^>]*>(.*?)</text>',
        src,
        re.S,
    )
    portrait = []
    for i, (y, fsize, txt) in enumerate(rows):
        portrait.append(
            f'<text class="f" style="animation-delay:{0.25 + i * 0.022:.3f}s;animation-duration:.35s" '
            f'xml:space="preserve" x="20" y="{y}" fill="{INK}" font-size="{fsize}" '
            f'textLength="800" lengthAdjust="spacing">{txt}</text>'
        )

    s = 0.43
    body = f"""
<defs>
  <linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="600" y2="0" gradientTransform="translate(-600 0)">
    <stop offset="0" stop-color="{INK}"/><stop offset=".42" stop-color="{INK}"/>
    <stop offset=".5" stop-color="{TECH}"/><stop offset=".58" stop-color="{INK}"/>
    <stop offset="1" stop-color="{INK}"/>
    <animateTransform attributeName="gradientTransform" type="translate" values="-600 0;600 0;600 0"
      keyTimes="0;.45;1" dur="7s" begin="1.6s" repeatCount="indefinite"/>
  </linearGradient>
</defs>
<rect width="{W}" height="{h}" rx="14" fill="{PAPER}"/>
<g class="f" {d(0)}>
  <rect class="live" x="48" y="49" width="8" height="8" rx="2" fill="{TECH}"/>
  <text x="66" y="57" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{MUTED}">CS ENGINEER &#183; AI &amp; FULL-STACK DEV</text>
</g>
<text class="r" {d(0.15)} x="44" y="188" font-family="{SERIF}" font-size="116" letter-spacing="-2.5" fill="{INK}">Amin</text>
<text class="r" {d(0.30)} x="44" y="288" font-family="{SERIF}" font-style="italic" font-size="116" letter-spacing="-2.5" fill="url(#shine)">Halitim</text>
<g class="r" {d(0.55)}>
  {text_lines(48, 338, ["I build full-stack backends, Flutter apps,", "and AI tools that solve real problems."], 26, f'font-family="{SANS}" font-size="17.5" fill="{INK_SOFT}"')}
</g>
<g class="f" {d(0.80)}>
  <text x="48" y="396" font-family="{MONO}" font-size="13" fill="{INK}">github.com/3boudi</text>
  <text class="nu" x="188" y="396" font-family="{MONO}" font-size="13" fill="{TECH}">&#8599;</text>
</g>
<g transform="translate(508 42) scale({s}) translate(-20 -37)" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">
  {''.join(portrait)}
</g>
"""
    write(
        "hero.svg",
        svg(
            W,
            h,
            body,
            ["serif", "serif-i", "sans", "mono"],
            "Amin Halitim (3boudi). CS Engineer, AI & Full-Stack Developer. I build full-stack backends, Flutter apps, and AI tools that solve real problems.",
        ),
    )


# ---- 2 · blue contribution graph --------------------------------------------
BLUE = [PAPER_DEEP, "#c8d3ff", "#94a8ff", "#6280ff", TECH, "#1a3be0"]


def level_for(c):
    if c <= 0:
        return 0
    if c <= 2:
        return 1
    if c <= 5:
        return 2
    if c <= 10:
        return 3
    if c <= 20:
        return 4
    return 5


def heatmap(data):
    days = data["days"]
    first = datetime.date.fromisoformat(days[0]["date"])
    lead = (first.weekday() + 1) % 7  # sunday = 0
    cell, step, gx, gy = 12, 15, 44, 96
    cells, months, seen = [], [], set()

    for i, day in enumerate(days):
        k = i + lead
        col, row = divmod(k, 7)
        date = datetime.date.fromisoformat(day["date"])
        if date.day <= 7 and (date.year, date.month) not in seen and row == 0:
            seen.add((date.year, date.month))
            months.append((col, date.strftime("%b")))
        c = day["count"]
        lvl = level_for(c)
        delay = 1.0 + col * 0.03 + row * 0.02
        cells.append(
            f'<rect class="p" style="animation-delay:{delay:.2f}s" x="{gx + col * step}" y="{gy + row * step}" '
            f'width="{cell}" height="{cell}" rx="3" fill="{BLUE[lvl]}">'
            f'<title>{day["date"]}: {c} contribution{"s" if c != 1 else ""}</title></rect>'
        )

    ncols = (len(days) + lead + 6) // 7
    right = gx + ncols * step - 3
    labels = "".join(
        f'<text x="{gx + col * step}" y="{gy + 7 * step + 16}" font-family="{MONO}" font-size="11" fill="{MUTED}">{m}</text>'
        for col, m in months
        if col < ncols - 12
    )
    legend_x = right - len(BLUE) * 14
    legend = "".join(
        f'<rect x="{legend_x + i * 14}" y="{gy + 7 * step + 6}" width="11" height="11" rx="2.5" fill="{col_hex}"/>'
        for i, col_hex in enumerate(BLUE)
    )
    h = gy + 7 * step + 44
    body = f"""
<rect width="{W}" height="{h}" rx="14" fill="{PAPER}"/>
<text class="r" {d(0.8)} x="42" y="62" font-family="{SERIF}" font-size="34" fill="{INK}">Every day, <tspan font-style="italic" fill="{TECH}">in blue</tspan></text>
<text class="f" {d(0.8)} x="{right}" y="60" text-anchor="end" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{MUTED}">REFRESHED DAILY</text>
{''.join(cells)}
<g class="f" {d(2.4)}>{labels}
<text x="{legend_x - 8}" y="{gy + 7 * step + 16}" text-anchor="end" font-family="{MONO}" font-size="11" fill="{MUTED}">less</text>
{legend}
<text x="{legend_x + len(BLUE) * 14 + 2}" y="{gy + 7 * step + 16}" font-family="{MONO}" font-size="11" fill="{MUTED}">more</text></g>
"""
    write(
        "heatmap.svg",
        svg(
            W,
            h,
            body,
            ["serif", "serif-i", "mono"],
            f'Contribution graph: {data["total_contributions"]:,} contributions in the last year',
        ),
    )


# ---- 3 · activity (monthly bars) --------------------------------------------
def activity(data):
    h = 340
    monthly = data["monthly"][-12:]
    top = max((m["total"] for m in monthly), default=1) or 1
    best_total = max(m["total"] for m in monthly)
    # Highlight the highest month (preferring the most recent peak if tied)
    best_idx = max(i for i, m in enumerate(monthly) if m["total"] == best_total)

    x0, x1, base, maxh, gap = 40, 600, 292, 140, 10
    bw = (x1 - x0 - gap * (len(monthly) - 1)) / len(monthly)
    bars = []
    for i, m in enumerate(monthly):
        partial = i == len(monthly) - 1
        is_best = i == best_idx
        bh = max(4, round(m["total"] / top * maxh))
        x = x0 + i * (bw + gap)
        fill = TECH if is_best else ("#c9c9c4" if partial else INK)
        label = datetime.date.fromisoformat(m["month"] + "-01").strftime("%b")
        bars.append(
            f'<rect class="g" style="animation-delay:{2.2 + i * 0.07:.2f}s" x="{x:.1f}" y="{base - bh}" '
            f'width="{bw:.1f}" height="{bh}" rx="4" fill="{fill}"><title>{label}: {m["total"]:,}</title></rect>'
            f'<text class="f" style="animation-delay:{2.2 + i * 0.07:.2f}s" x="{x + bw / 2:.1f}" y="{base + 22}" '
            f'text-anchor="middle" font-family="{MONO}" font-size="11" fill="{MUTED}">{label}</text>'
        )
        if is_best:
            bars.append(
                f'<text class="p" style="animation-delay:3.2s" x="{x + bw / 2:.1f}" y="{base - bh - 10}" '
                f'text-anchor="middle" font-family="{MONO}" font-size="11" fill="{TECH}">{m["total"]:,}</text>'
            )

    cs = data["current_streak"]["length"]
    ls = data["longest_streak"]["length"]
    if cs > 0:
        streak_big = f'{cs} <tspan font-style="italic">days</tspan>'
        streak_note = "current streak, and the longest" if cs >= ls else f"current streak, longest {ls}"
    else:
        streak_big = f'{ls} <tspan font-style="italic">days</tspan>'
        streak_note = "longest streak this year"

    total_days = len(data["days"])
    stats = [
        (streak_big, streak_note),
        (f'{data["active_days"]}<tspan fill="#8e8e93"> / {total_days}</tspan>', "days with a commit"),
        (f'{data["best_day"]["count"]}', "on the busiest day"),
    ]
    side = []
    for i, (big, small) in enumerate(stats):
        y = 104 + i * 92
        side.append(
            f'<g class="r" {d(2.6 + i * 0.15)}>'
            f'<text x="650" y="{y}" font-family="{SERIF}" font-size="40" fill="{INK}">{big}</text>'
            f'<text x="650" y="{y + 24}" font-family="{SANS}" font-size="13" fill="{MUTED}">{escape(small)}</text></g>'
        )
        if i < 2:
            side.append(f'<rect class="f" {d(2.6)} x="650" y="{y + 44}" width="190" height="1" fill="{RULE}"/>')

    body = f"""
<rect width="{W}" height="{h}" rx="14" fill="{PAPER}"/>
<text class="f" {d(1.9)} x="40" y="58" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{MUTED}">THE LAST 12 MONTHS ON GITHUB</text>
<text class="r" {d(2.0)} x="38" y="114" font-family="{SERIF}" font-size="52" fill="{INK}">{data["total_contributions"]:,} <tspan font-style="italic">contributions</tspan></text>
{''.join(bars)}
{''.join(side)}
"""
    write(
        "activity.svg",
        svg(
            W,
            h,
            body,
            ["serif", "serif-i", "sans", "mono"],
            f'{data["total_contributions"]:,} contributions in the last year, {ls}-day longest streak',
        ),
    )


# ---- 4 · three world tiles --------------------------------------------------
TILE_W, TILE_H = W / 3 - 8, 210  # 285.333px: two exact 12px gaps across 880px


def count_up(num, word, x, y, attrs, begin, dur=1.1, frames=18):
    """Count up from 0 using 18 SMIL <set> frames with cubic ease-out (works inside <img>)."""
    m = re.match(r"([\d.]+)(.*)", str(num))
    val, suf = float(m.group(1)), m.group(2)
    dec = len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
    tail = f' <tspan font-style="italic">{escape(word)}</tspan>'
    if os.environ.get("STATIC"):
        return f'<text x="{x}" y="{y}" {attrs}>{escape(str(num))}{tail}</text>'
    out = []
    for i in range(frames + 1):
        e = 1 - (1 - i / frames) ** 3
        txt = str(num) if i == frames else f"{val * e:.{dec}f}{suf}"
        on = begin + dur * i / frames
        off = (
            ""
            if i == frames
            else f'<set attributeName="opacity" to="0" begin="{begin + dur * (i + 1) / frames:.3f}s"/>'
        )
        out.append(
            f'<text x="{x}" y="{y}" {attrs} opacity="0">{escape(txt)}{tail}'
            f'<set attributeName="opacity" to="1" begin="{on:.3f}s"/>{off}</text>'
        )
    return "".join(out)


def tile(name, label, color, on, num, word, blurb, delay, pos):
    lines = wrap(blurb, 33)
    blurb_svg = "".join(
        f'<text class="r" {d(delay + 0.75 + i * 0.1)} x="24" y="{148 + i * 20}" font-family="{SANS}" '
        f'font-size="14" fill="{on}" opacity=".92">{escape(line)}</text>'
        for i, line in enumerate(lines)
    )
    body = f"""
<defs>
  <clipPath id="card"><rect width="{TILE_W:.3f}" height="{TILE_H}" rx="14"/></clipPath>
  <clipPath id="slot"><rect x="0" y="62" width="{TILE_W:.3f}" height="62"/></clipPath>
  <linearGradient id="gl" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>
    <stop offset=".5" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
</defs>
<g class="ti" {d(delay)}>
  <g clip-path="url(#card)">
    <rect width="{TILE_W:.3f}" height="{TILE_H}" fill="{color}"/>
    <circle class="rg" {d(delay + 0.5)} cx="{TILE_W - 40:.1f}" cy="{TILE_H - 40}" r="60" fill="none" stroke="{on}" stroke-opacity=".5" stroke-width="2"/>
    <rect class="sh" style="animation-delay:{delay + 1.4:.2f}s" x="0" y="-20" width="90" height="{TILE_H + 40}" fill="url(#gl)" transform="translate(-260 0)"/>
  </g>
  <text class="sl" {d(delay + 0.35)} x="24" y="38" font-family="{MONO}" font-size="12" letter-spacing="1.2" fill="{on}">{escape(label)}</text>
  <g class="ai" {d(delay + 0.5)}><text class="n" style="animation-delay:{delay + 1.3:.2f}s" x="248" y="38" font-family="{MONO}" font-size="14" fill="{on}">&#8594;</text></g>
  <g clip-path="url(#slot)"><g class="ro" {d(delay + 0.45)}>
    {count_up(num, word, 22, 112, f'font-family="{SERIF}" font-size="44" fill="{on}"', delay + 0.45)}
  </g></g>
  {blurb_svg}
</g>
"""
    write(
        f"{name}.svg",
        svg(
            TILE_W,
            TILE_H,
            body,
            ["serif", "serif-i", "sans", "mono"],
            f"{label}: {num} {word}. {blurb}",
            left=4 * pos,
            right=8 - 4 * pos,
        ),
    )


# ---- 5 · editorial core stack card (value-add) ------------------------------
def stack_card(profile):
    h = 276
    langs = profile.get("languages") or {}
    lang_total = max(1, len(langs))

    # Proportional animated ecosystem bar reflecting 3boudi's repo & stack breadth
    segments = [
        ("Backend & AI", 27, TECH),
        ("Web & TS", 32, STUDIO),
        ("Mobile & Flutter", 15, LEARN),
        ("PHP & SQL", 16, INK),
        ("Systems & CS", 10, "#8e8e93"),
    ]
    bar_x, bar_y, bar_w, bar_h = 40, 116, 800, 10
    segs_svg = []
    cx = bar_x
    for idx, (seg_name, pct, col) in enumerate(segments):
        sw = bar_w * pct / 100.0
        segs_svg.append(
            f'<rect class="gx" style="animation-delay:{3.95 + idx * 0.08:.2f}s" '
            f'x="{cx:.1f}" y="{bar_y}" width="{sw + 0.5:.1f}" height="{bar_h}" fill="{col}">'
            f"<title>{escape(seg_name)}</title></rect>"
        )
        cx += sw

    columns = [
        (
            "BACKEND & AI",
            TECH,
            [
                "Python · FastAPI · SQLModel",
                "PostgreSQL · PostGIS · Redis",
                "Docker · REST / OpenAPI · AI",
            ],
        ),
        (
            "MOBILE & WEB",
            STUDIO,
            [
                "Flutter · Dart · Mobile UX",
                "TypeScript · React · Tailwind",
                "JavaScript · Electron · Vite",
            ],
        ),
        (
            "SYSTEMS & CS",
            LEARN,
            [
                "C · C++ · Java · PHP / Laravel",
                "TCP / UDP Sockets · OMNeT++",
                "Algorithms · Git · CI / CD",
            ],
        ),
    ]

    cols_svg = []
    col_xs = [40, 316, 592]
    for i, (title, dot_col, rows) in enumerate(columns):
        x = col_xs[i]
        delay = 4.05 + i * 0.12
        if i > 0:
            cols_svg.append(
                f'<rect class="f" {d(4.0)} x="{x - 24}" y="150" width="1" height="92" fill="{RULE}"/>'
            )
        rows_svg = "".join(
            f'<text x="{x}" y="{190 + j * 24}" font-family="{SANS}" font-size="14" fill="{INK_SOFT}">{escape(r)}</text>'
            for j, r in enumerate(rows)
        )
        cols_svg.append(
            f'<g class="r" {d(delay)}>'
            f'<rect x="{x}" y="152" width="8" height="8" rx="2" fill="{dot_col}"/>'
            f'<text x="{x + 16}" y="160" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{INK}">{escape(title)}</text>'
            f"{rows_svg}</g>"
        )

    body = f"""
<defs>
  <clipPath id="stackbar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="5"/></clipPath>
</defs>
<rect width="{W}" height="{h}" rx="14" fill="{PAPER}"/>
<text class="f" {d(3.80)} x="40" y="48" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{MUTED}">CORE STACK &amp; ENGINEERING</text>
<text class="f" {d(3.85)} x="840" y="48" text-anchor="end" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{MUTED}">{lang_total}+ LANGUAGES &#183; FULL STACK</text>
<text class="r" {d(3.85)} x="38" y="94" font-family="{SERIF}" font-size="38" fill="{INK}">Tools behind <tspan font-style="italic" fill="{TECH}">the systems</tspan></text>
<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="5" fill="{PAPER_DEEP}"/>
<g clip-path="url(#stackbar)">{''.join(segs_svg)}</g>
{''.join(cols_svg)}
"""
    write(
        "stack.svg",
        svg(
            W,
            h,
            body,
            ["serif", "serif-i", "sans", "mono"],
            "Core stack and engineering tooling: Backend & AI, Mobile & Web, Systems & CS.",
        ),
    )


# ---- 6 · section title + 6 featured repo cards ------------------------------
REPO_W, REPO_H = W / 3 - 8, 182
FEATURED_REPOS = [
    (
        "AVL-BST",
        "AVL-BST",
        "Interactive AVL & Binary Search Tree visualizer built with Canvas and Electron.",
        "JavaScript",
        TECH,
        False,
    ),
    (
        "amin-GPT",
        "amin-GPT",
        "Fast, secure AI chatbot with serverless Netlify backend and Cloudflare Turnstile.",
        "TypeScript",
        STUDIO,
        True,
    ),
    (
        "fallah-tech-backend-system",
        "fallah-tech-backend",
        "FieldShift Planner: FastAPI, PostGIS & Redis backend for climate-resilient agronomy.",
        "Python",
        LEARN,
        True,
    ),
    (
        "Contact_application",
        "Contact_application",
        "Full-stack Flutter mobile app backed by FastAPI & PostgreSQL with auth and calling.",
        "Dart",
        TECH,
        False,
    ),
    (
        "PyChat-Network-System-",
        "PyChat-Network-System",
        "TCP & UDP client-server socket models with a multi-threaded real-time terminal chat.",
        "Python",
        STUDIO,
        False,
    ),
    (
        "product_mangement_system",
        "product_management",
        "Modular REST API powered by FastAPI, SQLModel, PostgreSQL, and FastAPI-Users auth.",
        "Python",
        LEARN,
        False,
    ),
]


def section_title(text, italic, theme):
    fg = "#e6edf3" if theme == "dark" else INK
    body = (
        f'<text class="r" {d(4.4)} x="2" y="46" font-family="{SERIF}" font-size="34" fill="{fg}">{escape(text)} '
        f'<tspan font-style="italic">{escape(italic)}</tspan></text>'
    )
    write(
        f"title-coding-{theme}.svg",
        svg(W, 64, body, ["serif", "serif-i"], f"{text} {italic}", bottom=0),
    )


def repo_card(idx, repo_name, display_name, desc, lang, color, is_live, stars):
    pos = idx % 3
    delay = 4.6 + idx * 0.11
    parts = [lang]
    if stars:
        parts.append(f"★ {stars}")
    if is_live:
        parts.append("live")
    meta = "  ·  ".join(parts)

    title_size = 18 if len(display_name) <= 17 else 16 if len(display_name) <= 21 else 15
    body = f"""
<rect width="{REPO_W:.3f}" height="{REPO_H}" rx="14" fill="{PAPER}"/>
<g class="r" {d(delay)}>
  <rect x="24" y="30" width="8" height="8" rx="2" fill="{color}"/>
  <text x="40" y="39" font-family="{SANS}" font-weight="600" font-size="{title_size}" fill="{INK}">{escape(display_name)}</text>
  {text_lines(24, 72, wrap(desc, 34), 21, f'font-family="{SANS}" font-size="14" fill="{INK_SOFT}"')}
  <text x="24" y="{REPO_H - 22}" font-family="{MONO}" font-size="12" fill="{MUTED}">{escape(meta)}</text>
</g>
"""
    write(
        f"repo-{repo_name}.svg",
        svg(
            REPO_W,
            REPO_H,
            body,
            ["sans", "sans-b", "mono"],
            f"{repo_name}: {desc}",
            left=4 * pos,
            right=8 - 4 * pos,
        ),
    )


def load_json(path, fallback=None):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    return fallback or {}


if __name__ == "__main__":
    contrib = load_json(CONTRIB_DATA)
    profile = load_json(PROFILE_DATA)

    original_repos = str(profile.get("original_repos", 64))
    total_stars = str(profile.get("total_stars", 93))
    years_str = f"{profile.get('years_on_github', 4)}+"
    created_year = profile.get("created_year", 2022)

    hero()
    heatmap(contrib)
    activity(contrib)
    tile(
        "build",
        "BUILD",
        TECH,
        "#ffffff",
        original_repos,
        "repos",
        "Full-stack apps in Python, FastAPI, PostgreSQL, Flutter & TypeScript.",
        3.10,
        0,
    )
    tile(
        "ship",
        "SHIP",
        STUDIO,
        "#ffffff",
        total_stars,
        "stars",
        "AI chatbots, agronomic backends, mobile apps & CS visualizers.",
        3.35,
        1,
    )
    tile(
        "craft",
        "CRAFT",
        LEARN,
        INK,
        years_str,
        "years",
        f"CS engineer & AI builder since {created_year}. GDGC Univ. Batna 2 workshops.",
        3.60,
        2,
    )
    stack_card(profile)
    section_title("What I'm", "coding", "dark")
    section_title("What I'm", "coding", "light")

    repo_meta = profile.get("repos") or {}
    for idx, (repo_name, display_name, desc, lang, color, is_live) in enumerate(FEATURED_REPOS):
        info = repo_meta.get(repo_name, {})
        stars = int(info.get("stars", 0))
        live_flag = is_live or bool(info.get("homepage"))
        repo_card(idx, repo_name, display_name, desc, lang, color, live_flag, stars)
