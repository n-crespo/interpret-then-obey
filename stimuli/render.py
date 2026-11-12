"""Draw one test case's image: the injection, in its representation, on a plain card.

PLACEHOLDER LAYOUT. The context content and where the injection sits in the image are not
specified yet (SPEC section 9), so every context renders the same card for now and only
the representation changes the pixels. Replace `draw_context` once context.json has fields.

Reproducibility: fonts are vendored in stimuli/fonts/ and Pillow is pinned in
stimuli/requirements.txt, so the same inputs give byte-identical PNGs on any OS.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from factors import FONTS_DIR, STIMULI_DIR, image_filename  # noqa: E402

PINNED_PILLOW = "13.0.0"  # keep in sync with stimuli/requirements.txt

WIDTH, HEIGHT = 720, 460
MARGIN = 50
FONT_SIZE = 36
LINE_GAP = 14
DEFAULT_FONT = "DejaVuSans.ttf"
BG, BORDER, INK = (242, 240, 235), (60, 60, 70), (20, 20, 25)


def get_font(name: str | None, size: int = FONT_SIZE) -> ImageFont.FreeTypeFont:
    path = FONTS_DIR / (name or DEFAULT_FONT)
    if not path.exists():
        raise FileNotFoundError(f"Vendored font missing: {path}. Do not substitute a system font; hashes would change.")
    return ImageFont.truetype(str(path), size)


def draw_context(img: Image.Image, context: dict) -> tuple[int, int, int, int]:
    """Draw the benign content and return the box (x0, y0, x1, y1) the injection goes in.

    Placeholder: a bordered card with the whole inner area free for the injection.
    """
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, WIDTH - 10, HEIGHT - 10], outline=BORDER, width=4)
    return MARGIN, MARGIN, WIDTH - MARGIN, HEIGHT - MARGIN


def draw_text(img: Image.Image, lines: list[str], font_name: str | None, box: tuple[int, int, int, int]) -> None:
    draw = ImageDraw.Draw(img)
    font = get_font(font_name)
    x0, y0, x1, y1 = box
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    total_h = len(lines) * line_h + (len(lines) - 1) * LINE_GAP
    if total_h > y1 - y0:
        raise ValueError(f"{len(lines)} lines do not fit in the injection box ({total_h}px > {y1 - y0}px)")
    y = y0 + (y1 - y0 - total_h) // 2
    for line in lines:
        w = draw.textlength(line, font=font)
        if w > x1 - x0:
            raise ValueError(f"line {line!r} is {w:.0f}px wide, injection box is {x1 - x0}px")
        draw.text((x0 + (x1 - x0 - w) / 2, y), line, font=font, fill=INK)
        y += line_h + LINE_GAP


def draw_images(img: Image.Image, paths: list[str], box: tuple[int, int, int, int]) -> None:
    """Lay pre-drawn images side by side, scaled to fit the box, in content order."""
    x0, y0, x1, y1 = box
    parts = [Image.open(STIMULI_DIR / p).convert("RGBA") for p in paths]
    gap = 20
    slot_w = (x1 - x0 - gap * (len(parts) - 1)) // len(parts)
    slot_h = y1 - y0
    x = x0
    for part in parts:
        scale = min(slot_w / part.width, slot_h / part.height)
        size = (max(1, round(part.width * scale)), max(1, round(part.height * scale)))
        part = part.resize(size, Image.Resampling.LANCZOS)
        img.paste(part, (x + (slot_w - size[0]) // 2, y0 + (slot_h - size[1]) // 2), part)
        x += slot_w + gap


def render_case(case: dict, out_dir: Path) -> Path:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    box = draw_context(img, case["context"])
    if case["format"] == "text":
        draw_text(img, case["content"], case["font"], box)
    else:
        draw_images(img, case["content"], box)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / image_filename(case)
    img.save(path, format="PNG", optimize=False)
    return path
