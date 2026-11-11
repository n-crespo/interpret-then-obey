#!/usr/bin/env python3
"""
Composite the symbol-section stimulus images (stimuli/symbols/manifest.json).

Every scene is the same base (red mug + blue notebook on a table) with the same
sign, and differs only in what is on the sign, so rows are comparable. The
payload is drawn at the same scale whether or not a legend sits below it. The
sign artwork lives in stimuli/src/symbols/ and is only cropped, scaled and
placed; nothing is redrawn here.

    python stimuli/render/generate_symbol_stimuli.py
        Draws a synthetic base scene.

    python stimuli/render/generate_symbol_stimuli.py --base photo.png --sign-box 140,20,1140,580
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

SIGN_BOX = (140, 20, 1140, 580)  # one sign for every scene
MARGIN = 36
PAYLOAD_H = 200  # the payload is fitted to this height in every scene
LEGEND_ART = "custom-opaque-legend.png"

# output file -> (payload artwork or None, legend on the sign?, mug and notebook in the scene?)
SCENES = {
    "sym-scene-nosign.png": None,
    "sym-scene-emoji.png": ("emoji.png", False, True),
    "sym-scene-common.png": ("common.png", False, True),
    "sym-scene-custom-clear.png": ("custom-clear.png", False, True),
    "sym-scene-custom-opaque.png": ("custom-opaque.png", False, True),
    "sym-scene-custom-opaque-legend.png": ("custom-opaque.png", True, True),
    # the legend on its own, shown in an earlier turn: same sign, no mug or notebook
    "sym-legend-custom-opaque.png": (None, True, False),
}


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


# ---- artwork helpers -------------------------------------------------------------------

def _ink(img: Image.Image) -> Image.Image:
    """Mask of everything that is not the white background."""
    diff = ImageChops.difference(img, Image.new("RGB", img.size, "white")).convert("L")
    return diff.point(lambda v: 255 if v > 24 else 0)


def _trim(img: Image.Image) -> Image.Image:
    bbox = _ink(img).getbbox()
    return img.crop(bbox) if bbox else img


def _load(name: str) -> Image.Image:
    art = Image.open(ART_DIR / name).convert("RGBA")
    out = Image.new("RGBA", art.size, (255, 255, 255, 255))
    out.alpha_composite(art)
    return _trim(out.convert("RGB"))


def _runs(mask: Image.Image, axis: str, min_gap: int) -> list[tuple[int, int]]:
    """Inked stretches along an axis; blank gaps shorter than min_gap do not split a stretch."""
    w, h = mask.size
    runs: list[list[int]] = []
    for i in range(h if axis == "y" else w):
        line = mask.crop((0, i, w, i + 1) if axis == "y" else (i, 0, i + 1, h))
        if line.getbbox() is None:
            continue
        if runs and i - runs[-1][1] <= min_gap:
            runs[-1][1] = i + 1
        else:
            runs.append([i, i + 1])
    return [(a, b) for a, b in runs]


def legend_parts() -> list[tuple[Image.Image, Image.Image]]:
    """Cut the legend artwork into (symbol, label) pairs, one per row, so the blank space
    inside it can be dropped and the labels drawn large."""
    art = _load(LEGEND_ART)
    parts = []
    for y0, y1 in _runs(_ink(art), "y", min_gap=40):
        row = art.crop((0, y0, art.width, y1))
        cols = _runs(_ink(row), "x", min_gap=60)
        if len(cols) != 2:
            raise ValueError(f"{LEGEND_ART}: expected a symbol and a label per row, found {len(cols)} pieces")
        (s0, s1), (l0, l1) = cols
        parts.append((_trim(row.crop((s0, 0, s1, row.height))), _trim(row.crop((l0, 0, l1, row.height)))))
    return parts


def _scaled(img: Image.Image, scale: float) -> Image.Image:
    return img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)


def _fit(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    return _scaled(img, min(max_w / img.width, max_h / img.height))


def legend_block(max_w: int, max_h: int, row_gap: int = 28, col_gap: int = 40) -> Image.Image:
    """Symbol column and label column, rows stacked. Both symbols share one scale and both
    labels share one scale; the labels are made as large as the space allows."""
    parts = legend_parts()
    row_h = (max_h - row_gap * (len(parts) - 1)) // len(parts)
    sym_scale = min(row_h / max(s.height for s, _ in parts), 0.3 * max_w / max(s.width for s, _ in parts))
    syms = [_scaled(s, sym_scale) for s, _ in parts]
    sym_w = max(s.width for s in syms)
    lab_scale = min((max_w - sym_w - col_gap) / max(l.width for _, l in parts), 0.8 * row_h / max(l.height for _, l in parts))
    labs = [_scaled(l, lab_scale) for _, l in parts]
    block = Image.new("RGB", (sym_w + col_gap + max(l.width for l in labs), row_h * len(parts) + row_gap * (len(parts) - 1)), "white")
    for i, (s, l) in enumerate(zip(syms, labs)):
        y = i * (row_h + row_gap)
        block.paste(s, ((sym_w - s.width) // 2, y + (row_h - s.height) // 2))
        block.paste(l, (sym_w + col_gap, y + (row_h - l.height) // 2))
    return block


def sign_card(size: tuple[int, int], payload: str | None, legend: bool) -> Image.Image:
    w, h = size
    card = Image.new("RGB", size, "white")
    zone_w = w - 2 * MARGIN
    if payload:
        art = _fit(_load(payload), zone_w, PAYLOAD_H)
        top = MARGIN if legend else (h - PAYLOAD_H) // 2
        card.paste(art, ((w - art.width) // 2, top + (PAYLOAD_H - art.height) // 2))
    if legend:
        top = MARGIN + PAYLOAD_H + 40 if payload else MARGIN
        if payload:
            ImageDraw.Draw(card).line([(MARGIN, top - 20), (w - MARGIN, top - 20)], fill=(150, 150, 150), width=2)
        block = legend_block(zone_w, h - MARGIN - top)
        card.paste(block, ((w - block.width) // 2, top + (h - MARGIN - top - block.height) // 2))
    ImageDraw.Draw(card).rectangle([0, 0, w - 1, h - 1], outline=(40, 40, 45), width=5)
    return card


def compose(base: Image.Image, payload: str | None, legend: bool, box, stand: bool) -> Image.Image:
    img = base.copy()
    x0, y0, x1, y1 = box
    if stand:  # two legs down to the table
        d = ImageDraw.Draw(img)
        for x in (x0 + 60, x1 - 60):
            d.rectangle([x - 7, y1, x + 7, TABLE_Y + 2], fill=(70, 70, 76))
        d.rectangle([x0 + 30, TABLE_Y - 4, x1 - 30, TABLE_Y + 6], fill=(70, 70, 76))  # stays behind the mug
    img.paste(sign_card((x1 - x0, y1 - y0), payload, legend), (x0, y0))
    return img


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_manifest(hashes: dict[str, str]) -> None:
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for row in rows:
        for item in [row, *(row.get("context") or [])]:
            if item.get("image"):
                item["image_sha256"] = hashes[Path(item["image"]).name]
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:  # LF on every OS, like build_manifest.py
        f.write(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")


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
        with_objects = Image.open(args.base).convert("RGB")
        box = tuple(int(v) for v in args.sign_box.split(","))
    else:
        with_objects = draw_base().resize((W, H), Image.LANCZOS).convert("RGB")
        box = SIGN_BOX
    backdrop = draw_base(objects=False).resize((W, H), Image.LANCZOS).convert("RGB")

    hashes = {}
    for name, spec in SCENES.items():
        if spec is None:
            out = with_objects
        else:
            payload, legend, objects = spec
            # the legend-only image always uses the drawn backdrop and the default sign position
            out = compose(with_objects, payload, legend, box, stand=not args.base) if objects else compose(backdrop, payload, legend, SIGN_BOX, stand=True)
        out.save(IMAGES_DIR / name, format="PNG")
        hashes[name] = sha256_file(IMAGES_DIR / name)

    for name, digest in hashes.items():
        print(f"{digest}  {name}")
    if args.update_manifest:
        update_manifest(hashes)
        print(f"Updated image_sha256 in {MANIFEST}")


if __name__ == "__main__":
    main()
