#!/usr/bin/env python3
"""Rebuild NotoSansSC-subset.otf: the Noto Sans CJK SC Bold glyphs the Mandarin
representation needs, plus printable ASCII. Committed so renders are identical on every
machine; this script only documents (and repeats) how the subset was made.

Usage: python stimuli/tools/make_cjk_subset.py /path/to/NotoSansCJK-Bold.ttc

If you add a Chinese rendition, add its characters to CHARS and rerun.
Face 2 of the Noto Sans CJK collection is the Simplified Chinese (SC) face.
"""
import sys
from pathlib import Path

from fontTools import subset

CHARS = "买一只熊。一台张给发消息：在大门口见我带去搜索提醒打电话保存照片笔记本脑礼品卡"
OUT = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "NotoSansSC-subset.otf"

src = sys.argv[1]
opts = subset.Options()
opts.layout_features = []
opts.name_IDs = ["*"]
opts.notdef_outline = True
opts.font_number = 2
font = subset.load_font(src, opts)
sub = subset.Subsetter(opts)
sub.populate(text=CHARS + "".join(chr(c) for c in range(0x20, 0x7F)))
sub.subset(font)
subset.save_font(font, str(OUT), opts)
print("wrote", OUT, OUT.stat().st_size, "bytes")
