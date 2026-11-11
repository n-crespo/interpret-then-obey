#!/usr/bin/env python3
"""
Render the stimulus images for the fictional-conlang section into stimuli/_bak/images/.

All sign text comes from stimuli/_bak/src (via stimuli/_bak/spec.py); nothing is typed in here.
Images carry only the stimulus itself: no English gloss, franchise tag, title that names
the language or script, or footer. The only header allowed is a short generic label set
per row in src/stimuli.json ("STORE HOURS", "NOTICE"); conlang signs have none.

Reproducibility: fonts are vendored in stimuli/fonts/ and Pillow is pinned in
stimuli/requirements.txt. Same Pillow version -> byte-identical PNGs on any OS, so
the image_sha256 values in the manifest stay valid after a re-render.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import PIL
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spec import FONTS_DIR, IMAGES_DIR, image_filename, load_rows  # noqa: E402

PINNED_PILLOW = "13.0.0"  # keep in sync with stimuli/requirements.txt

WIDTH, HEIGHT = 720, 460
HEADER_X, HEADER_Y, HEADER_RULE_Y = 45, 50, 82
BODY_X = 50
LINE_H = 54
TEXT_MAX_W = WIDTH - 2 * BODY_X
TEXT_MAX_Y = HEIGHT - 40  # bottom of the last line must stay inside every frame

DEFAULT_COLORS = {"bg": (242, 240, 235), "border": (60, 60, 70), "text": (20, 20, 25), "accent": (170, 40, 30)}


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load the vendored DejaVu font so renders are identical on every OS."""
    path = FONTS_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    if not path.exists():
        raise FileNotFoundError(f"Vendored font missing: {path}. Do not substitute a system font; hashes would change.")
    return ImageFont.truetype(str(path), size)


def draw_frame(draw: ImageDraw.ImageDraw, theme: str, c: dict) -> None:
    w, h = WIDTH, HEIGHT
    if theme == "scifi_hud":  # spacecraft UI / terminal
        draw.rectangle([15, 15, w - 15, h - 15], outline=c["border"], width=4)
        draw.rectangle([22, 22, w - 22, h - 22], outline=tuple(v // 2 for v in c["border"]), width=1)
        for (x1, y1), (x2, y2) in [((15, 45), (45, 15)), ((w - 15, 45), (w - 45, 15)),
                                   ((15, h - 45), (45, h - 15)), ((w - 15, h - 45), (w - 45, h - 15))]:
            draw.line([(x1, y1), (x2, y2)], fill=c["accent"], width=3)
    elif theme == "sticky_note":  # desk memo
        draw.rectangle([25, 25, w - 25, h - 25], fill=c["bg"], outline=(210, 200, 100), width=3)
        draw.rectangle([25, 25, w - 25, 48], fill=(235, 225, 110))
    elif theme == "game_card":  # trading card / collector plate
        draw.rectangle([15, 15, w - 15, h - 15], outline=c["border"], width=6)
        draw.rectangle([24, 24, w - 24, h - 24], outline=c["accent"], width=2)
    elif theme == "plaque":  # wall plaque
        draw.rectangle([20, 20, w - 20, h - 20], outline=c["border"], width=5)
        draw.rectangle([28, 28, w - 28, h - 28], outline=(180, 175, 165), width=2)
    elif theme == "notice":  # printed bulletin
        draw.rectangle([20, 20, w - 20, h - 20], outline=c["border"], width=4)
    else:
        raise ValueError(f"unknown theme {theme!r}")


def draw_text_checked(draw, xy, text, font, fill, where: str) -> None:
    if draw.textlength(text, font=font) > TEXT_MAX_W:
        raise ValueError(f"{where}: text overflows the sign: {text!r}")
    if xy[1] + LINE_H > TEXT_MAX_Y:
        raise ValueError(f"{where}: too many lines for the sign: {text!r}")
    draw.text(xy, text, fill=fill, font=font)


def draw_tengwar_glyphs(draw: ImageDraw.ImageDraw) -> None:
    """Decorative Tengwar-style strokes. They do not encode the phrase."""
    color = (40, 60, 80)
    strokes = [
        (100, 240, 145, 240), (145, 210, 145, 320),
        (190, 240, 235, 240), (190, 240, 190, 330), (235, 240, 235, 330),
        (280, 230, 315, 265), (315, 265, 280, 300), (315, 215, 315, 320),
        (360, 240, 405, 240), (405, 215, 405, 330),
        (450, 240, 485, 265), (485, 265, 450, 300), (485, 205, 485, 340),
        (530, 240, 575, 240), (530, 215, 530, 330), (575, 215, 575, 330),
    ]
    for x1, y1, x2, y2 in strokes:
        draw.line([(x1, y1), (x2, y2)], fill=color, width=5)
        draw.ellipse([(x2 - 4, y2 - 4), (x2 + 4, y2 + 4)], fill=color)

    tehtar = [(125, 210), (210, 215), (300, 200), (385, 195), (465, 190), (550, 195)]
    for tx, ty in tehtar:
        draw.ellipse([(tx - 5, ty - 5), (tx + 5, ty + 5)], fill=(170, 50, 30))
        draw.arc([(tx - 10, ty - 10), (tx + 10, ty + 6)], start=0, end=180, fill=(170, 50, 30), width=3)


def draw_piqad_glyphs(draw: ImageDraw.ImageDraw) -> None:
    """Decorative pIqaD-style shapes. They do not encode the phrase."""
    color = (220, 45, 35)
    glyphs = [
        [(95, 270), (120, 210), (150, 270), (128, 258), (95, 270)],
        [(175, 215), (210, 215), (192, 265), (180, 265)],
        [(235, 225), (270, 225), (270, 280), (252, 262)],
        [(295, 270), (320, 210), (350, 235), (320, 270)],
        [(375, 215), (410, 215), (392, 275), (375, 275)],
        [(435, 230), (470, 230), (482, 272), (448, 272)],
        [(510, 210), (540, 242), (510, 278), (498, 260)],
    ]
    for polygon in glyphs:
        draw.polygon(polygon, outline=color, fill=(50, 15, 10))
        cx = sum(p[0] for p in polygon) // len(polygon)
        cy = sum(p[1] for p in polygon) // len(polygon)
        draw.line([(cx - 10, cy - 10), (cx + 10, cy + 10)], fill=color, width=4)


GLYPHS = {"tengwar": draw_tengwar_glyphs, "piqad": draw_piqad_glyphs}


def body_top(n_lines: int, has_header: bool) -> int:
    """Short signs (<= 2 lines) are centred vertically; longer ones start under the header."""
    if n_lines <= 2:
        return max(110, (HEIGHT - n_lines * LINE_H) // 2 + (20 if has_header else 0))
    return 135 if has_header else 160


def render_row(row: dict, out_dir: Path = IMAGES_DIR) -> Path:
    r = row["render"]
    colors = {k: tuple(r.get(k, v)) for k, v in DEFAULT_COLORS.items()}

    img = Image.new("RGB", (WIDTH, HEIGHT), color=colors["bg"])
    draw = ImageDraw.Draw(img)
    draw_frame(draw, r["theme"], colors)

    header = r.get("header")
    if header:
        draw_text_checked(draw, (HEADER_X, HEADER_Y), header, get_font(22, bold=True), colors["accent"], row["id"])
        draw.line([(HEADER_X, HEADER_RULE_Y), (WIDTH - HEADER_X, HEADER_RULE_Y)], fill=colors["border"], width=1)

    if "glyphs" in r:
        # Glyph signs show only the script strokes; the phrase stays in the manifest.
        GLYPHS[r["glyphs"]](draw)
    else:
        body_font = get_font(28, bold=True)
        y = body_top(len(row["lines"]), bool(header))
        for line in row["lines"]:
            draw_text_checked(draw, (BODY_X, y), line, body_font, colors["text"], row["id"])
            y += LINE_H

    path = out_dir / image_filename(row)
    img.save(path, format="PNG")
    return path


def render_all(out_dir: Path = IMAGES_DIR) -> None:
    if PIL.__version__ != PINNED_PILLOW:
        warnings.warn(f"Pillow {PIL.__version__} != pinned {PINNED_PILLOW}; output may not match manifest hashes.",
                      stacklevel=1)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [r for r in load_rows() if r["medium"] == "image"]
    for row in rows:
        render_row(row, out_dir)
    print(f"Rendered {len(rows)} stimuli to {out_dir}")


if __name__ == "__main__":
    render_all()
