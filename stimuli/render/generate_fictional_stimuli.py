#!/usr/bin/env python3
"""
Render the stimulus images for the fictional-conlang section into stimuli/images/.

All sign text comes from stimuli/src (via stimuli/spec.py); nothing is typed in here.

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
MARGIN_X = 42
TEXT_MAX_W = WIDTH - 2 * MARGIN_X
FOOTER = "[ AR Assistant View - Fictional Language Benchmark ]"

DEFAULT_COLORS = {"bg": (240, 240, 245), "border": (60, 60, 80), "text": (20, 20, 30), "accent": (180, 40, 40)}


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load the vendored DejaVu font so renders are identical on every OS."""
    path = FONTS_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    if not path.exists():
        raise FileNotFoundError(f"Vendored font missing: {path}. Do not substitute a system font; hashes would change.")
    return ImageFont.truetype(str(path), size)


def draw_frame(draw: ImageDraw.ImageDraw, theme: str, c: dict) -> None:
    w, h = WIDTH, HEIGHT
    if theme == "scifi_hud":
        draw.rectangle([15, 15, w - 15, h - 15], outline=c["border"], width=4)
        draw.rectangle([22, 22, w - 22, h - 22], outline=tuple(v // 2 for v in c["border"]), width=1)
        for (x1, y1), (x2, y2) in [((15, 45), (45, 15)), ((w - 15, 45), (w - 45, 15)),
                                   ((15, h - 45), (45, h - 15)), ((w - 15, h - 45), (w - 45, h - 15))]:
            draw.line([(x1, y1), (x2, y2)], fill=c["accent"], width=3)
    elif theme == "fan_merch":
        draw.rectangle([18, 18, w - 18, h - 18], outline=c["border"], width=5)
        draw.rectangle([25, 25, w - 25, h - 25], outline=(200, 200, 200), width=1)
    elif theme == "sticky_note":
        draw.rectangle([25, 25, w - 25, h - 25], fill=c["bg"], outline=(210, 200, 100), width=3)
        draw.rectangle([25, 25, w - 25, 45], fill=(235, 225, 110))
    elif theme == "game_card":
        draw.rectangle([15, 15, w - 15, h - 15], outline=c["border"], width=6)
        draw.rectangle([24, 24, w - 24, h - 24], outline=c["accent"], width=2)
    elif theme == "convention_badge":
        draw.rectangle([20, 20, w - 20, h - 20], outline=c["border"], width=4)
    else:
        raise ValueError(f"unknown theme {theme!r}")


def draw_text_checked(draw, xy, text, font, fill, where: str) -> None:
    if draw.textlength(text, font=font) > TEXT_MAX_W:
        raise ValueError(f"{where}: text overflows the sign: {text!r}")
    draw.text(xy, text, fill=fill, font=font)


def draw_tengwar_glyphs(draw: ImageDraw.ImageDraw) -> None:
    """Decorative Tengwar-style strokes. They do not encode the phrase."""
    color = (40, 70, 90)
    strokes = [
        (100, 260, 140, 260), (140, 235, 140, 325),
        (180, 260, 220, 260), (180, 260, 180, 335), (220, 260, 220, 335),
        (260, 250, 290, 280), (290, 280, 260, 310), (290, 240, 290, 325),
        (330, 260, 370, 260), (370, 240, 370, 335),
        (410, 260, 440, 280), (440, 280, 410, 310), (440, 230, 440, 345),
        (480, 260, 520, 260), (480, 240, 480, 335), (520, 240, 520, 335),
    ]
    for x1, y1, x2, y2 in strokes:
        draw.line([(x1, y1), (x2, y2)], fill=color, width=4)
        draw.ellipse([(x2 - 3, y2 - 3), (x2 + 3, y2 + 3)], fill=color)

    tehtar = [(120, 240), (200, 245), (280, 230), (350, 225), (425, 220), (500, 225)]
    for tx, ty in tehtar:
        draw.ellipse([(tx - 4, ty - 4), (tx + 4, ty + 4)], fill=(180, 60, 30))
        draw.arc([(tx - 8, ty - 8), (tx + 8, ty + 4)], start=0, end=180, fill=(180, 60, 30), width=2)


def draw_piqad_glyphs(draw: ImageDraw.ImageDraw) -> None:
    """Decorative pIqaD-style shapes. They do not encode the phrase."""
    color = (220, 50, 40)
    glyphs = [
        [(100, 290), (120, 240), (145, 290), (125, 280), (100, 290)],
        [(165, 245), (195, 245), (180, 285), (170, 285)],
        [(220, 250), (250, 250), (250, 295), (235, 280)],
        [(275, 290), (295, 240), (320, 260), (295, 290)],
        [(345, 245), (375, 245), (360, 295), (345, 295)],
        [(400, 255), (430, 255), (440, 290), (410, 290)],
        [(465, 240), (490, 265), (465, 295), (455, 280)],
    ]
    for polygon in glyphs:
        draw.polygon(polygon, outline=color, fill=(60, 15, 10))
        cx = sum(p[0] for p in polygon) // len(polygon)
        cy = sum(p[1] for p in polygon) // len(polygon)
        draw.line([(cx - 8, cy - 8), (cx + 8, cy + 8)], fill=color, width=3)


GLYPHS = {"tengwar": draw_tengwar_glyphs, "piqad": draw_piqad_glyphs}


def render_row(row: dict, out_dir: Path = IMAGES_DIR) -> Path:
    r = row["render"]
    colors = {k: tuple(r.get(k, v)) for k, v in DEFAULT_COLORS.items()}
    theme = r["theme"]

    img = Image.new("RGB", (WIDTH, HEIGHT), color=colors["bg"])
    draw = ImageDraw.Draw(img)
    draw_frame(draw, theme, colors)

    tag_font = get_font(14, bold=True)
    header_font = get_font(20, bold=True)
    body_font = get_font(23, bold=True)
    sub_font = get_font(14)

    tag = r["tag"]
    draw.rectangle([40, 32, 40 + len(tag) * 10 + 20, 56], fill=colors["accent"])
    draw.text((48, 36), tag.upper(), fill=(255, 255, 255), font=tag_font)

    title_color = (160, 40, 20) if theme == "sticky_note" else colors["accent"]
    draw_text_checked(draw, (MARGIN_X, 68), r["title"], header_font, title_color, row["id"])
    draw.line([(MARGIN_X, 98), (WIDTH - MARGIN_X, 98)], fill=colors["border"], width=1)

    # The phrase itself must fit. sign_lines / gloss_lines are drawn unchecked: several
    # of the committed bracketed captions already run past the margin, and checking them
    # here would force those images (and their hashes) to change.
    if "sign_lines" in r:
        checked, unchecked = [], r["sign_lines"]
    else:
        checked, unchecked = row["lines"], r.get("gloss_lines", [])
    y = 135
    for line in checked:
        draw_text_checked(draw, (MARGIN_X, y), line, body_font, colors["text"], row["id"])
        y += 44
    for line in unchecked:
        draw.text((MARGIN_X, y), line, fill=colors["text"], font=body_font)
        y += 44

    if "glyphs" in r:
        GLYPHS[r["glyphs"]](draw)

    draw.text((MARGIN_X, HEIGHT - 42), FOOTER, fill=(120, 120, 130), font=sub_font)

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
