#!/usr/bin/env python3
"""
Convert a portrait image (default: assets/avatar.png) into a clean monochrome
ASCII-art SVG (assets/portrait-ascii.svg) whose <text> rows are ingested by
scripts/render_readme_cards.py for the terminal print-in hero animation.

For the circular pixel-art GitHub avatar, cleanly isolates the bust silhouette
(wavy hair, face, beard, ear, hoodie, shoulders) from the outer frame, sky,
pine tree, and background door so the portrait floats naturally in monochrome
ink on the warm paper hero card.
"""
from collections import deque
import html
import math
import os
import sys
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "assets", "avatar.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "assets", "portrait-ascii.svg")

COLS = int(os.environ.get("COLS", 148))
ART_W = 800
CELL_W = ART_W / COLS
CELL_H = CELL_W * 15 / 8
ROWS = round(COLS * 8 / 15)

# Bright (sparse) -> Dark (dense); leading space keeps background clean paper
RAMP = " .`:-=+*cs#%@"

PAD = 20
ART_TOP = 37


def isolate_bust(im):
    """Isolate the bust silhouette cleanly on white and lift midtone hair/hoodie detail."""
    w, h = im.size
    px = im.load()
    cx, cy = w / 2.0, h / 2.0
    max_r = min(w, h) * 0.482

    # Build background mask via flood-fill from exterior + clean shoulder/sky bounds
    bg = [[False] * w for _ in range(h)]

    def is_hard_bg(x, y):
        if math.hypot(x - cx, y - cy) > max_r:
            return True
        # Above head
        if y < 48:
            return True
        # Above-left of left shoulder diagonal: from (138, 286) down to (56, 386)
        if x < 142 and y >= 220 and y < 286 + (138 - x) * 1.18:
            return True
        # Above-right of right shoulder diagonal: from (352, 260) down to (424, 344)
        if x > 350 and y < 260 + (x - 352) * 1.15:
            return True
        # Right of top-right hair crown
        if x > 328 and y < 120:
            return True
        # Far-left sky/tree outside leftmost wavy lock
        if x < 95 and y < 325:
            return True
        return False

    q = deque()
    for y in range(h):
        for x in range(w):
            if is_hard_bg(x, y):
                bg[y][x] = True
                q.append((x, y))

    # Flood-fill sky, sunset, pine tree, and wooden door pixels connected to exterior
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not bg[ny][nx]:
                r, g, b = px[nx, ny]
                sky_purple = (b > g + 2) and (ny < 270)
                tree_green = (g >= r - 2) and (nx < 165) and (ny < 340)
                sunset_orange = (r > 165 and g > 50 and nx < 155 and ny < 295)
                top_speck = (ny < 110) and ((r > 110 and nx < 165) or (r > 95 and nx > 290))
                left_cheek_bg = (nx < 142 and 190 <= ny <= 295 and (r > 115 or b > 18 or g > 25))
                right_door_edge = (nx > 344 and ny < 272 and r > 55)
                if sky_purple or tree_green or sunset_orange or top_speck or left_cheek_bg or right_door_edge:
                    bg[ny][nx] = True
                    q.append((nx, ny))

    # Keep only the single largest connected foreground component (eliminates stray sky specks)
    visited = [[False] * w for _ in range(h)]
    best_comp = []
    for y in range(h):
        for x in range(w):
            if not bg[y][x] and not visited[y][x]:
                comp = []
                cq = deque([(x, y)])
                visited[y][x] = True
                while cq:
                    ux, uy = cq.popleft()
                    comp.append((ux, uy))
                    for vx, vy in ((ux + 1, uy), (ux - 1, uy), (ux, uy + 1), (ux, uy - 1)):
                        if 0 <= vx < w and 0 <= vy < h and not bg[vy][vx] and not visited[vy][vx]:
                            visited[vy][vx] = True
                            cq.append((vx, vy))
                if len(comp) > len(best_comp):
                    best_comp = comp

    fg = [[False] * w for _ in range(h)]
    for x, y in best_comp:
        fg[y][x] = True

    # Build rich tonal grayscale image inside the bust silhouette
    # Lift dark hair/hoodie tones with non-linear curve so folds & curls stay legible in ASCII
    gray = Image.new("L", (w, h), 255)
    gpx = gray.load()
    fg_lums = []
    for y in range(h):
        for x in range(w):
            if fg[y][x]:
                r, g, b = px[x, y]
                fg_lums.append(0.299 * r + 0.587 * g + 0.114 * b)
    hi = max(fg_lums) if fg_lums else 255.0
    lo = min(fg_lums) if fg_lums else 0.0
    span = max(1.0, hi - lo)

    for y in range(h):
        for x in range(w):
            if not fg[y][x]:
                gpx[x, y] = 255
                continue
            r, g, b = px[x, y]
            lum = (0.299 * r + 0.587 * g + 0.114 * b - lo) / span
            # Lift darks smoothly (sqrt-like curve) so wavy hair & hoodie folds show rich texture
            lum = pow(max(0.0, min(1.0, lum)), 0.72)
            # Map foreground into [18..228] so even sunlit face stays lightly stippled, never vanishing
            val = 18 + lum * 208
            # Gentle fade along the bottom circular arc
            dist = math.hypot(x - cx, y - cy)
            if dist > max_r - 18:
                t = (dist - (max_r - 18)) / 18.0
                val = val * (1 - t) + 255 * t
            gpx[x, y] = int(max(0, min(255, val)))

    # Mild unsharp mask to accentuate pixel-art hair curls, beard edge, and collar
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=2))
    # Re-zero exterior to pure white after sharpening
    gpx = gray.load()
    for y in range(h):
        for x in range(w):
            if not fg[y][x]:
                gpx[x, y] = 255
    return gray


def build_ascii_svg(src_path, out_path):
    im = Image.open(src_path).convert("RGB")
    gray = isolate_bust(im)
    sampled = gray.resize((COLS, ROWS), Image.LANCZOS)
    px = sampled.load()

    white_floor = 0.94
    gamma = 1.08

    rows_txt = []
    for y in range(ROWS):
        line = []
        for x in range(COLS):
            lum = px[x, y] / 255.0
            if lum >= white_floor:
                line.append(" ")
                continue
            val = pow(lum / white_floor, gamma)
            idx = int((1.0 - val) * (len(RAMP) - 1) + 0.5)
            idx = max(0, min(len(RAMP) - 1, idx))
            line.append(RAMP[idx])
        rows_txt.append("".join(line))

    canvas_w = ART_W + PAD * 2
    canvas_h = ART_TOP + ROWS * CELL_H + PAD
    font_size = CELL_H * 0.88

    lines_svg = []
    for ry, line in enumerate(rows_txt):
        if not line.strip():
            continue
        y = ART_TOP + ry * CELL_H + CELL_H * 0.74
        lines_svg.append(
            f'<text xml:space="preserve" x="{PAD}" y="{y:.2f}" fill="#111111" '
            f'font-size="{font_size:.2f}" textLength="{ART_W}" lengthAdjust="spacing">'
            f"{html.escape(line)}</text>"
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.1f}" height="{canvas_h:.1f}" '
        f'viewBox="0 0 {canvas_w:.1f} {canvas_h:.1f}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">'
        f'<rect width="100%" height="100%" fill="#f3f3f1"/>'
        f'{"".join(lines_svg)}'
        f"</svg>"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {out_path} ({len(svg) // 1024} KB, {len(lines_svg)} non-empty rows, {COLS} cols)")


if __name__ == "__main__":
    build_ascii_svg(SRC, OUT)
