#!/usr/bin/env python3
"""
Composite the symbol-section stimulus images (stimuli/symbols/manifest.json).

Every scene is the same base (red mug + blue notebook on a table) and differs
only in what is on the sign, so rows are comparable. The sign artwork lives in
stimuli/src/symbols/ and is pasted unchanged; nothing is redrawn here.

    python stimuli/render/generate_symbol_stimuli.py
        Draws a synthetic base scene.

    python stimuli/render/generate_symbol_stimuli.py --base photo.png --sign-box 400,120,900,460
        Uses a real photo as the base (it should show no sign) and pastes each
        sign as a white card into the given x0,y0,x1,y1 box.

    --update-manifest   also write image_sha256 into stimuli/symbols/manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import warnings
from pathlib import Path

import PIL
from PIL import Image, ImageChops, ImageDraw, ImageFilter

STIMULI_DIR = Path(__file__).resolve().parents[1]
IMAGES_DIR = STIMULI_DIR / "images"
ART_DIR = STIMULI_DIR / "src" / "symbols"
MANIFEST = STIMULI_DIR / "symbols" / "manifest.json"
PINNED_PILLOW = "13.0.0"  # keep in sync with stimuli/requirements.txt

W, H = 1280, 960
SS = 2  # supersample factor for the drawn scene
TABLE_Y = 600

# output file -> (artwork files stacked top to bottom on the sign, sign box x0,y0,x1,y1)
WIDE = (330, 190, 950, 570)
TALL = (400, 30, 880, 580)
SCENES = {
    "sym-scene-nosign.png": None,
    "sym-scene-emoji.png": (["emoji.png"], WIDE),
    "sym-scene-common.png": (["common.png"], WIDE),
    "sym-scene-custom-clear.png": (["custom-clear.png"], WIDE),
    "sym-scene-custom-opaque.png": (["custom-opaque.png"], WIDE),
    "sym-scene-custom-opaque-legend.png": (["custom-opaque.png", "custom-opaque-legend.png"], TALL),
}
LEGEND_IMAGE = ("sym-legend-custom-opaque.png", ["custom-opaque-legend.png"], (290, 110, 990, 700))


def _s(*v):
    return [x * SS for x in v]


def _shadow(img, box, blur=18, alpha=90):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(_s(*box), fill=(0, 0, 0, alpha))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur * SS)))


def draw_base(objects: bool = True) -> Image.Image:
    """Wall, table and (optionally) the red mug and blue notebook."""
    img = Image.new("RGBA", (W * SS, H * SS), (226, 222, 214, 255))
    d = ImageDraw.Draw(img)
    for y in range(TABLE_Y * SS):  # soft wall gradient
        t = y / (TABLE_Y * SS)
        d.line([(0, y), (W * SS, y)], fill=(int(232 - 14 * t), int(229 - 14 * t), int(222 - 14 * t), 255))
    d.rectangle(_s(0, TABLE_Y, W, H), fill=(176, 132, 88, 255))
    for y in range(TABLE_Y, H, 46):  # plank lines
        d.line(_s(0, y, W, y), fill=(160, 118, 76, 255), width=SS)
    d.rectangle(_s(0, TABLE_Y, W, TABLE_Y + 6), fill=(150, 108, 68, 255))
    if not objects:
        return img

    # red mug, front left
    _shadow(img, (150, 800, 470, 860))
    d = ImageDraw.Draw(img)
    red, red_dark, red_rim = (206, 32, 38, 255), (150, 20, 26, 255), (228, 70, 74, 255)
    d.arc(_s(350, 670, 470, 800), start=270, end=90, fill=red, width=26 * SS)
    d.rectangle(_s(190, 640, 390, 820), fill=red)
    d.ellipse(_s(190, 790, 390, 850), fill=red)
    d.ellipse(_s(190, 610, 390, 670), fill=red_rim)
    d.ellipse(_s(204, 618, 376, 662), fill=red_dark)

    # blue notebook, lying flat, front right
    _shadow(img, (760, 800, 1180, 870))
    d = ImageDraw.Draw(img)
    blue, blue_dark, page = (36, 84, 190, 255), (22, 56, 140, 255), (240, 238, 230, 255)
    d.polygon(_s(800, 720, 1110, 700, 1170, 830, 830, 856), fill=blue)
    d.polygon(_s(830, 856, 1170, 830, 1170, 846, 830, 872), fill=page)
    d.polygon(_s(800, 720, 830, 856, 830, 872, 800, 736), fill=blue_dark)
    d.line(_s(1076, 703, 1136, 833), fill=(20, 20, 30, 255), width=6 * SS)  # elastic band
    return img


def _flatten(path: Path) -> Image.Image:
    art = Image.open(path).convert("RGBA")
    out = Image.new("RGBA", art.size, (255, 255, 255, 255))
    out.alpha_composite(art)
    out = out.convert("RGB")
    # trim the artwork's own white border so the symbols fill the sign
    bbox = ImageChops.difference(out, Image.new("RGB", out.size, "white")).getbbox()
    return out.crop(bbox) if bbox else out


def sign_card(art_files: list[str], size: tuple[int, int], margin: int = 44) -> Image.Image:
    """White card with the artwork scaled to fit, stacked top to bottom."""
    w, h = size
    card = Image.new("RGB", size, "white")
    arts = [_flatten(ART_DIR / f) for f in art_files]
    gap = 24 if len(arts) > 1 else 0
    avail_w, avail_h = w - 2 * margin, h - 2 * margin - gap * (len(arts) - 1)
    scale = min(min(avail_w / a.width for a in arts), avail_h / sum(a.height for a in arts))
    arts = [a.resize((round(a.width * scale), round(a.height * scale)), Image.LANCZOS) for a in arts]
    y = margin + (avail_h - sum(a.height for a in arts)) // 2
    for i, a in enumerate(arts):
        card.paste(a, ((w - a.width) // 2, y))
        y += a.height + gap
        if i < len(arts) - 1:
            ImageDraw.Draw(card).line([(margin, y - gap // 2), (w - margin, y - gap // 2)], fill=(150, 150, 150), width=2)
    ImageDraw.Draw(card).rectangle([0, 0, w - 1, h - 1], outline=(40, 40, 45), width=5)
    return card


def compose(base: Image.Image, art_files: list[str] | None, box, stand: bool) -> Image.Image:
    img = base.copy()
    if art_files:
        x0, y0, x1, y1 = box
        if stand:  # two legs down to the table
            d = ImageDraw.Draw(img)
            for x in (x0 + 60, x1 - 60):
                d.rectangle([x - 7, y1, x + 7, TABLE_Y + 14], fill=(70, 70, 76))
            d.rectangle([x0 + 30, TABLE_Y + 8, x1 - 30, TABLE_Y + 20], fill=(70, 70, 76))
        img.paste(sign_card(art_files, (x1 - x0, y1 - y0)), (x0, y0))
    return img


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_manifest(hashes: dict[str, str]) -> None:
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for row in rows:
        for item in [row, *(row.get("context") or [])]:
            if item.get("image"):
                item["image_sha256"] = hashes[Path(item["image"]).name]
    MANIFEST.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", help="photo to use as the scene instead of the drawn one")
    ap.add_argument("--sign-box", help="x0,y0,x1,y1 of the sign in --base (required with --base)")
    ap.add_argument("--update-manifest", action="store_true")
    args = ap.parse_args(argv)
    if PIL.__version__ != PINNED_PILLOW:
        warnings.warn(f"Pillow {PIL.__version__} != pinned {PINNED_PILLOW}: image hashes will not match the manifest", stacklevel=2)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    if args.base:
        if not args.sign_box:
            ap.error("--sign-box is required with --base")
        base = Image.open(args.base).convert("RGB")
        user_box = tuple(int(v) for v in args.sign_box.split(","))
    else:
        base = draw_base().resize((W, H), Image.LANCZOS).convert("RGB")
        user_box = None

    hashes = {}
    for name, spec in SCENES.items():
        art, box = spec if spec else (None, None)
        out = compose(base, art, user_box or box, stand=not args.base)
        out.save(IMAGES_DIR / name, format="PNG")
        hashes[name] = sha256_file(IMAGES_DIR / name)

    # the legend on its own (shown in an earlier turn): a sign close-up, no mug or notebook
    name, art, box = LEGEND_IMAGE
    backdrop = draw_base(objects=False).resize((W, H), Image.LANCZOS).convert("RGB")
    compose(backdrop, art, box, stand=False).save(IMAGES_DIR / name, format="PNG")
    hashes[name] = sha256_file(IMAGES_DIR / name)

    for name, digest in hashes.items():
        print(f"{digest}  {name}")
    if args.update_manifest:
        update_manifest(hashes)
        print(f"Updated image_sha256 in {MANIFEST}")


if __name__ == "__main__":
    main()
