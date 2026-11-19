#!/usr/bin/env python3
"""
Download SIL OFL Google Fonts (Instrument Serif, Geist, Geist Mono), verify each
font's OpenType name table (so regular vs. italic can never swap), and subset to
printable ASCII + UI punctuation/arrows/stars as compact WOFF files in fonts/.
"""
import io
import os
import re
import urllib.request
from fontTools.subset import Subsetter, Options
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(HERE, "..", "fonts")

CSS_URLS = [
    "https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&display=swap",
    "https://fonts.googleapis.com/css2?family=Geist:wght@400;600&family=Geist+Mono:wght@400&display=swap",
]

# Target font mapping keyed by (family, style, weight) -> (filename, expected_subfamily_substring)
TARGETS = {
    ("Instrument Serif", "normal", 400): ("serif-400.woff", "Regular"),
    ("Instrument Serif", "italic", 400): ("serif-italic.woff", "Italic"),
    ("Geist", "normal", 400): ("geist-400.woff", "Regular"),
    ("Geist", "normal", 600): ("geist-600.woff", "SemiBold"),
    ("Geist Mono", "normal", 400): ("geistmono-400.woff", "Regular"),
}

# Printable ASCII + middle dot, en/em dash, smart quotes, ellipsis, arrows, star
UNICODES = (
    list(range(0x0020, 0x007F))
    + [0x00B7, 0x2013, 0x2014, 0x2018, 0x2019, 0x2026, 0x2605]
    + list(range(0x2190, 0x219A))
)


def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read()


def parse_font_faces(css_text):
    found = {}
    for block in re.findall(r"@font-face\s*\{([^}]+)\}", css_text, re.S):
        fam = re.search(r"font-family:\s*'([^']+)'", block)
        sty = re.search(r"font-style:\s*(\w+)", block)
        wt = re.search(r"font-weight:\s*(\d+)", block)
        src = re.search(r"url\(([^)]+)\)", block)
        if fam and sty and wt and src:
            key = (fam.group(1), sty.group(1), int(wt.group(1)))
            found[key] = src.group(1).strip("'\"")
    return found


def subset_to_woff(ttf_bytes, out_path, expected_subfamily):
    font = TTFont(io.BytesIO(ttf_bytes))
    # Verify OpenType name table (nameID 1 = family, nameID 2 = subfamily, nameID 4 = full name)
    name_table = font["name"]
    fam = name_table.getDebugName(1) or ""
    sub = name_table.getDebugName(2) or ""
    full = name_table.getDebugName(4) or ""
    is_italic = bool(font["head"].macStyle & 2) or ("italic" in sub.lower()) or ("italic" in full.lower())

    want_italic = expected_subfamily.lower() == "italic"
    if want_italic != is_italic:
        raise RuntimeError(
            f"Font italic mismatch for {out_path}: expected {expected_subfamily}, "
            f"got family={fam!r}, subfamily={sub!r}, full={full!r}"
        )

    opts = Options()
    opts.flavor = "woff"
    opts.desubroutinize = True
    opts.hinting = False
    opts.drop_tables += ["DSIG"]
    opts.layout_features = ["kern", "liga"]
    subsetter = Subsetter(options=opts)
    subsetter.populate(unicodes=UNICODES)
    subsetter.subset(font)
    font.save(out_path)
    size = os.path.getsize(out_path)
    print(f"OK {os.path.basename(out_path):18s} | {fam} [{sub}] (full={full}) | {size / 1024:.1f} KB")


def main():
    os.makedirs(FONTS_DIR, exist_ok=True)
    discovered = {}
    for url in CSS_URLS:
        css = fetch_bytes(url).decode("utf-8")
        discovered.update(parse_font_faces(css))

    for key, (filename, expected_sub) in TARGETS.items():
        if key not in discovered:
            raise RuntimeError(f"Could not find font face {key} in Google Fonts CSS")
        ttf_bytes = fetch_bytes(discovered[key])
        out_path = os.path.join(FONTS_DIR, filename)
        subset_to_woff(ttf_bytes, out_path, expected_sub)


if __name__ == "__main__":
    main()
