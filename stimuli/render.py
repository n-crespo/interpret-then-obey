"""Drawing one stimulus image: a context card with the injection box in its lower part.

Rendering must be deterministic across platforms, or the image hashes in
stimuli/manifest.jsonl stop matching. Everything here depends
only on the arguments, the vendored fonts in stimuli/assets/fonts/ and the pinned Pillow.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from stimuli.paths import FONTS_DIR, REPO_ROOT

if TYPE_CHECKING:
    from stimuli.schema import Context, Rendition, Representation

WIDTH, HEIGHT = 720, 460
INJECTION_BOX_TOP = 265
INJECTION_BOX_BOTTOM = 425

# Injection text is drawn in one face and size, so legibility does not vary between
# representations. A monospace face because in DejaVu Sans Bold capital I and
# lowercase l look the same (issue #48). Representations whose script it lacks
# (Ge'ez, CJK) name their own `font`, drawn at a larger size: their glyphs sit
# much smaller in the em box, and are hard to read at 28px.
INJECTION_FONT = "DejaVuSansMono-Bold.ttf"
INJECTION_FONT_SIZE = 28
SCRIPT_FONT_SIZE = 44


def get_font(size: int, bold: bool = False, font_name: str | None = None) -> ImageFont.FreeTypeFont:
    """Load a vendored font from stimuli/assets/fonts/ (DejaVu Sans unless `font_name` is given).

    The layout engine is pinned to BASIC. Pillow's default is RAQM when libraqm is
    available (Linux/macOS wheels) and BASIC when it is not (Windows wheels), and the two
    place glyphs differently, so the default would make pixels depend on the platform.
    BASIC does no bidi or complex shaping.
    """
    if font_name is None:
        font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    font_path = FONTS_DIR / font_name
    if not font_path.exists():
        raise FileNotFoundError(f"Missing vendored font: {font_path}")
    return ImageFont.truetype(str(font_path), size, layout_engine=ImageFont.Layout.BASIC)


# Per-context colours: background, frame, accent, injection box fill, injection box border.
PALETTES = {
    "library_board": ((244, 242, 238), (70, 75, 80), (40, 70, 110), (235, 233, 228), (180, 175, 170)),
    "product_info": ((246, 248, 250), (60, 80, 100), (30, 90, 140), (238, 242, 246), (160, 180, 200)),
    "advertisement": ((255, 250, 242), (180, 50, 40), (190, 45, 35), (252, 244, 232), (220, 180, 160)),
}


def render_stimulus_image(
    image_path: Path,
    context: Context,
    representation: Representation,
    rendition: Rendition | None,
) -> None:
    """Render a stimulus image combining context content and the injection rendition.

    For the baseline (format 'none', rendition None) everything up to and including the
    empty injection box is drawn exactly as for an injected image, and nothing is put in
    the box, so the two differ only inside it.
    """
    if context.id not in PALETTES:
        raise ValueError(f"Context {context.id!r} has no palette in stimuli/render.py PALETTES")
    bg_color, border_color, accent_color, box_bg, box_border = PALETTES[context.id]

    img = Image.new("RGB", (WIDTH, HEIGHT), color=bg_color)
    draw = ImageDraw.Draw(img)

    # 1. Outer Frame
    draw.rectangle([16, 16, WIDTH - 16, HEIGHT - 16], outline=border_color, width=4)
    draw.rectangle([24, 24, WIDTH - 24, HEIGHT - 24], outline=(border_color[0]//2, border_color[1]//2, border_color[2]//2), width=1)

    # 2. Context Section
    header_font = get_font(size=22, bold=True)
    body_font = get_font(size=18, bold=False)

    header = context.header
    draw.text((45, 42), header, fill=accent_color, font=header_font)
    draw.line([(45, 74), (WIDTH - 45, 74)], fill=border_color, width=2)

    for i, line in enumerate(context.lines):
        draw.text((45, 95 + (i * 38)), line, fill=(30, 30, 35), font=body_font)

    # 3. Injection Box (Lower Inset Area)
    draw.rectangle(
        [40, INJECTION_BOX_TOP, WIDTH - 40, INJECTION_BOX_BOTTOM],
        fill=box_bg,
        outline=box_border,
        width=2,
    )

    # Decorative accent corner notches on injection frame
    draw.line([(40, INJECTION_BOX_TOP + 15), (40 + 15, INJECTION_BOX_TOP)], fill=accent_color, width=2)
    draw.line([(WIDTH - 40, INJECTION_BOX_TOP + 15), (WIDTH - 40 - 15, INJECTION_BOX_TOP)], fill=accent_color, width=2)
    draw.line([(40, INJECTION_BOX_BOTTOM - 15), (40 + 15, INJECTION_BOX_BOTTOM)], fill=accent_color, width=2)
    draw.line([(WIDTH - 40, INJECTION_BOX_BOTTOM - 15), (WIDTH - 40 - 15, INJECTION_BOX_BOTTOM)], fill=accent_color, width=2)

    # 4. Render Injection Payload (nothing for the baseline)
    if representation.is_baseline:
        pass
    elif representation.format == "text":
        content = rendition.content
        fonts = [
            get_font(size=SCRIPT_FONT_SIZE, font_name=representation.font)
            if representation.uses_font(idx)
            else get_font(size=INJECTION_FONT_SIZE, font_name=INJECTION_FONT)
            for idx in range(len(content))
        ]
        total_text_h = len(content) * 44
        box_h = INJECTION_BOX_BOTTOM - INJECTION_BOX_TOP
        start_y = INJECTION_BOX_TOP + max(20, (box_h - total_text_h) // 2)

        # Fail rather than draw past the injection box (inside its 2px border).
        ascent, descent = fonts[-1].getmetrics()
        text_bottom = start_y + (len(content) - 1) * 44 + ascent + descent
        if text_bottom > INJECTION_BOX_BOTTOM - 2:
            raise ValueError(
                f"{len(content)} lines do not fit in the injection box "
                f"(text ends at y={text_bottom}, box ends at y={INJECTION_BOX_BOTTOM - 2})"
            )
        max_text_w = WIDTH - 2 * 50  # 10px inside the box on each side

        for idx, (line, inj_font) in enumerate(zip(content, fonts)):
            # Center text horizontally in the box
            text_w = draw.textlength(line, font=inj_font)
            if text_w > max_text_w:
                raise ValueError(f"line {line!r} is {text_w:.0f}px wide, injection box allows {max_text_w}px")
            start_x = max(50, (WIDTH - text_w) // 2)
            draw.text((start_x, start_y + (idx * 44)), line, fill=(20, 20, 25), font=inj_font)

    elif representation.format == "image":
        # Load and paste pre-drawn asset centered in injection box
        asset_path = REPO_ROOT / rendition.content[0]
        asset_img = Image.open(asset_path).convert("RGBA")

        box_w = WIDTH - 80
        box_h = INJECTION_BOX_BOTTOM - INJECTION_BOX_TOP

        # Scale down if asset exceeds box dimensions
        w, h = asset_img.size
        scale = min(1.0, (box_w - 40) / w, (box_h - 20) / h)
        if scale < 1.0:
            new_size = (int(w * scale), int(h * scale))
            asset_img = asset_img.resize(new_size, Image.Resampling.LANCZOS)
            w, h = new_size

        paste_x = (WIDTH - w) // 2
        paste_y = INJECTION_BOX_TOP + (box_h - h) // 2
        img.paste(asset_img, (paste_x, paste_y), mask=asset_img.split()[3])

    image_path.parent.mkdir(parents=True, exist_ok=True)
    # compress_level=0 writes stored (uncompressed) deflate blocks. The zlib-ng builds in
    # Pillow's Windows and Linux wheels produce different compressed bytes for the same
    # pixels at every level from 1 to 9, so only level 0 gives the same file, and the same
    # image_sha256, on every platform. Pillow writes no metadata chunks here.
    img.save(image_path, format="PNG", compress_level=0)
