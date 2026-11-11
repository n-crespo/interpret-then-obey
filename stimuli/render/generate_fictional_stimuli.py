#!/usr/bin/env python3
"""
Render the stimulus images for the fictional-conlang section into stimuli/images/.

All sign text comes from stimuli/src (via stimuli/spec.py); nothing is typed in here.
Images show only the conlang text, never an English translation.

Reproducibility: fonts are vendored in stimuli/fonts/ and Pillow is pinned in
stimuli/requirements.txt. Same Pillow version -> byte-identical PNGs on any OS, so
the image_sha256 values in the manifest stay valid after a re-render.
"""

from __future__ import annotations

import sys
import unicodedata
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


# ---------------------------------------------------------------------------
# Invented-glyph ciphers. These are NOT real Tengwar or pIqaD: each letter maps
# to a deterministic, distinct invented glyph styled after the script, so the
# image genuinely encodes the phrase (and injection/benign images differ).
# ---------------------------------------------------------------------------

LATIN_ALPHABET = "abcdefghijklmnopqrstuvwxyz"
# Klingon's 26 letters in pIqaD order; multi-char letters are matched first.
KLINGON_ALPHABET = ["a", "b", "ch", "D", "e", "gh", "H", "I", "j", "l", "m", "n", "ng",
                    "o", "p", "q", "Q", "r", "S", "t", "tlh", "u", "v", "w", "y", "'"]
PUNCT = set(".,!?-")


def tokenize_latin(text: str) -> list[tuple[str, bool]]:
    """-> [(token, has_diacritic)]; token is a base letter, ' ', or punctuation."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFD", ch)
        letter = base[0].lower()
        if letter in LATIN_ALPHABET or letter in PUNCT or letter in " '":
            out.append((letter, len(base) > 1))
        else:
            raise ValueError(f"no glyph for {ch!r} in {text!r}")
    return out


def tokenize_klingon(text: str) -> list[tuple[str, bool]]:
    out, i = [], 0
    by_len = sorted(KLINGON_ALPHABET, key=len, reverse=True)
    while i < len(text):
        for letter in by_len:
            if text.startswith(letter, i):
                out.append((letter, False))
                i += len(letter)
                break
        else:
            ch = text[i]
            if ch in PUNCT or ch == " ":
                out.append((ch, False))
                i += 1
            else:
                raise ValueError(f"no pIqaD-style glyph for {ch!r} in {text!r}")
    return out


def tengwar_glyph(draw, x: int, base: int, idx: int, accent: bool, color, mark_color) -> int:
    stem, bows, mark = idx % 3, (idx // 3) % 3, (idx // 9) % 3
    sx = x + 3
    if stem == 1:
        draw.line([(sx, base - 22), (sx, base + 16)], fill=color, width=3)
    elif stem == 2:
        draw.line([(sx, base - 40), (sx, base)], fill=color, width=3)
    else:
        draw.line([(sx, base - 22), (sx, base)], fill=color, width=3)
    if bows == 0:
        draw.arc([(sx - 2, base - 22), (sx + 14, base)], start=270, end=90, fill=color, width=3)
    elif bows == 1:
        draw.arc([(sx - 2, base - 22), (sx + 10, base)], start=270, end=90, fill=color, width=3)
        draw.arc([(sx + 6, base - 22), (sx + 18, base)], start=270, end=90, fill=color, width=3)
    else:
        draw.ellipse([(sx, base - 20), (sx + 14, base - 2)], outline=color, width=3)
    if mark == 1:
        draw.ellipse([(sx + 5, base - 32), (sx + 10, base - 27)], fill=mark_color)
    elif mark == 2:
        draw.arc([(sx + 1, base - 36), (sx + 15, base - 26)], start=180, end=360, fill=mark_color, width=2)
    if accent:
        draw.line([(sx + 8, base - 46), (sx + 14, base - 52)], fill=mark_color, width=2)
    return 26


def piqad_glyph(draw, x: int, base: int, idx: int, color, fill) -> int:
    shapes = [
        [(0, 34), (8, 0), (22, 34)],
        [(0, 30), (10, 0), (22, 8), (14, 34)],
        [(0, 0), (22, 6), (18, 24), (6, 34), (0, 18)],
    ]
    shape, orient, mark = shapes[idx % 3], (idx // 3) % 3, (idx // 9) % 3
    pts = []
    for px, py in shape:
        if orient == 1:
            px = 22 - px
        elif orient == 2:
            py = 34 - py
        pts.append((x + px, base - 34 + py))
    draw.polygon(pts, outline=color, fill=fill, width=2)
    cx, cy = x + 11, base - 17
    if mark == 1:
        draw.line([(cx - 6, cy - 6), (cx + 6, cy + 6)], fill=color, width=3)
    elif mark == 2:
        draw.ellipse([(cx - 3, cy - 3), (cx + 3, cy + 3)], fill=color)
    return 30


def draw_punct(draw, x: int, base: int, tok: str, color) -> int:
    if tok in ".,":
        n = 2 if tok == "." else 1
        for k in range(n):
            draw.ellipse([(x + 2, base - 4 - k * 10), (x + 7, base + 1 - k * 10)], fill=color)
    elif tok in "!?":
        draw.line([(x + 4, base - 30), (x + 4, base - 10)], fill=color, width=3)
        draw.ellipse([(x + 2, base - 5), (x + 7, base)], fill=color)
    elif tok == "-":
        draw.line([(x + 1, base - 14), (x + 9, base - 14)], fill=color, width=3)
    elif tok == "'":
        draw.line([(x + 4, base - 38), (x + 2, base - 28)], fill=color, width=2)
    return 14


def draw_cipher(draw, row: dict, colors: dict) -> None:
    script = row["script"]
    text = row["text"]
    tokens = tokenize_klingon(text) if script == "piqad_style_cipher" else tokenize_latin(text)

    # group into words so we only wrap between words
    words, cur = [], []
    for tok in tokens:
        if tok[0] == " ":
            if cur:
                words.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        words.append(cur)

    if script == "tengwar_style_cipher":
        color, mark_color = (40, 70, 90), (180, 60, 30)
        index = LATIN_ALPHABET.index

        def glyph(x, base, tok):
            return tengwar_glyph(draw, x, base, index(tok[0]), tok[1], color, mark_color)
    elif script == "piqad_style_cipher":
        color, fill = colors["accent"], tuple(max(0, v // 4) for v in colors["accent"])
        index = KLINGON_ALPHABET.index
        mark_color = color

        def glyph(x, base, tok):
            return piqad_glyph(draw, x, base, index(tok[0]), color, fill)
    else:
        raise ValueError(f"{row['id']}: unknown cipher script {script!r}")

    glyph_w = 26 if script == "tengwar_style_cipher" else 30

    def is_punct(tok) -> bool:
        # In Klingon the apostrophe is a letter (glottal stop) and gets a glyph.
        return tok[0] in PUNCT or (tok[0] == "'" and script != "piqad_style_cipher")

    x, base, row_step, word_gap = MARGIN_X, 190, 72, 22
    for word in words:
        ww = sum(14 if is_punct(t) else glyph_w for t in word)
        if x > MARGIN_X and x + ww > WIDTH - MARGIN_X:
            x, base = MARGIN_X, base + row_step
        if base > HEIGHT - 70:
            raise ValueError(f"{row['id']}: cipher text does not fit on the sign")
        for tok in word:
            if is_punct(tok):
                x += draw_punct(draw, x, base, tok[0], mark_color)
            else:
                x += glyph(x, base, tok)
        x += word_gap


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

    tag = r["tag"].upper()
    tag_w = draw.textlength(tag, font=tag_font)
    draw.rectangle([40, 32, 40 + tag_w + 16, 56], fill=colors["accent"])
    draw.text((48, 36), tag, fill=(255, 255, 255), font=tag_font)

    title_color = (160, 40, 20) if theme == "sticky_note" else colors["accent"]
    draw_text_checked(draw, (MARGIN_X, 68), r["title"], header_font, title_color, row["id"])
    draw.line([(MARGIN_X, 98), (WIDTH - MARGIN_X, 98)], fill=colors["border"], width=1)

    if row["script"].endswith("_cipher"):
        draw_cipher(draw, row, colors)
    else:
        for i, line in enumerate(row["lines"]):
            draw_text_checked(draw, (MARGIN_X, 135 + i * 44), line, body_font, colors["text"], row["id"])

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
