"""The interpretation-gradient representations (obfuscated, keyed, plus the
extra natural-language and Klingon variants) say what they claim to say.

A wrong ciphertext would silently turn a "can the model decode it" row into an
"is this even decodable" row, so every encoding is decoded here and compared with
the English rendition of the same injection.
"""

import base64
import codecs
import sys
from pathlib import Path

STIMULI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STIMULI.parent))
from stimuli.load import expand_injections, load_factors, rendition_of  # noqa: E402

FACTORS = load_factors()
BUYS = [i for i in expand_injections(FACTORS).values() if i.command.id == "buy"]


def _content(rep_id, injection):
    rendition = rendition_of(FACTORS.representations[rep_id], injection)
    return list(rendition.content) if rendition else None


def _rendered(rep_id):
    """(English sentence, this representation's content) for each buy injection it renders."""
    out = []
    for inj in BUYS:
        content = _content(rep_id, inj)
        if content is not None:
            out.append((_content("english", inj)[0], content))
    assert out, f"{rep_id} renders no buy injection"
    return out


def _words(sentence):
    return sentence.rstrip(".").lower().split()


def test_meaning_matches_the_decoded_encodings():
    for meaning, c in _rendered("rot13"):
        assert codecs.decode(c[0], "rot13") == meaning
    for meaning, c in _rendered("base64"):
        assert base64.b64decode(c[0]).decode() == meaning
    for meaning, c in _rendered("reversed"):
        assert c[0][::-1] == meaning
    for meaning, c in _rendered("a1z26_key"):
        assert ["".join(chr(96 + int(n)) for n in w.split("-")) for w in " ".join(c[:-1]).split()] == _words(meaning)


def test_scramble_decodes():
    for rep in ("scrambled", "scrambled_full"):
        for meaning, c in _rendered(rep):
            got, want = c[0].rstrip(".").split(), meaning.rstrip(".").split()
            assert [sorted(w.lower()) for w in got] == [sorted(w.lower()) for w in want]


def test_full_scramble_moves_every_letter():
    for meaning, c in _rendered("scrambled_full"):
        for got, want in zip(c[0].rstrip(".").lower().split(), _words(meaning)):
            if len(want) > 1:
                assert all(a != b for a, b in zip(got, want)), (got, want)


def test_labeled_variants_wrap_the_same_payload():
    for inj in BUYS:
        c = {r: _content(r, inj) for r in ("rot13_labeled", "klingon_latin", "klingon_latin_lexicon")}
        if c["rot13_labeled"]:
            assert c["rot13_labeled"][0] == "ROT13: " + codecs.encode(_content("english", inj)[0], "rot13")
        if c["klingon_latin_lexicon"]:
            assert c["klingon_latin_lexicon"][0] == c["klingon_latin"][0]


LATIN_TWINS = {"russian_latin": "russian", "greek_latin": "greek", "mandarin_pinyin": "mandarin", "amharic_latin": "amharic"}


def test_latin_twins_render_the_same_injections_as_their_originals():
    """A Latin twin changes only the script, so it covers exactly its original's injections."""
    injections = expand_injections(FACTORS, include_excluded=True).values()
    for twin, original in LATIN_TWINS.items():
        covered = {r: {i.id for i in injections if _content(r, i)} for r in (twin, original)}
        assert covered[twin] == covered[original], twin
        assert FACTORS.representations[twin].language == FACTORS.representations[original].language


def test_latin_twins_transliterate_their_originals():
    """Russian (BGN/PCGN) and Greek (ELOT 743, unaccented) romanize letter by letter."""
    cyr = dict(zip("а б в г д е ж з и й к л м н о п р с т у ф х ц ч ш ы э ю я".split(),
                   "a b v g d e zh z i y k l m n o p r s t u f kh ts ch sh y e yu ya".split()))
    grk = dict(zip("α β γ δ ε ζ η θ ι κ λ μ ν ξ ο π ρ σ ς τ υ φ χ ψ ω ά έ ή ί ό ύ ώ".split(),
                   "a v g d e z i th i k l m n x o p r s s t y f ch ps o a e i i o y o".split()))
    for twin, table in (("russian_latin", cyr), ("greek_latin", grk)):
        for inj in expand_injections(FACTORS, include_excluded=True).values():
            if not (src := _content(LATIN_TWINS[twin], inj)):
                continue
            want = "".join(table.get(ch, ch) for ch in src[0].lower().replace("ου", "ou").replace("ού", "ou"))
            assert _content(twin, inj)[0].lower() == want, (twin, inj.id)


def test_fonts_cover_every_line_they_draw():
    """Each line's font (the representation's own, or the default injection font) has every glyph; a missing one would render as tofu."""
    from PIL import Image, ImageDraw

    from stimuli.render import INJECTION_FONT, INJECTION_FONT_SIZE, SCRIPT_FONT_SIZE, get_font

    def ink(font_name, ch):
        size = INJECTION_FONT_SIZE if font_name == INJECTION_FONT else SCRIPT_FONT_SIZE
        img = Image.new("L", (100, 100), 0)
        ImageDraw.Draw(img).text((10, 10), ch, font=get_font(size, font_name=font_name), fill=255)
        return img.tobytes()

    for rep in FACTORS.representations.values():
        if rep.format != "text":
            continue
        for injection in expand_injections(FACTORS).values():
            rendition = rendition_of(rep, injection)
            for idx, line in enumerate(rendition.content if rendition else []):
                font_name = rep.font if rep.uses_font(idx) else INJECTION_FONT
                notdef = ink(font_name, "͸")
                for ch in line:
                    if not ch.isspace():
                        assert ink(font_name, ch) != notdef, f"{rep.id}: U+{ord(ch):04X} missing from {font_name}"
