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


MORSE = dict(zip("abcdefghijklmnopqrstuvwxyz", ".- -... -.-. -.. . ..-. --. .... .. .--- -.- .-.. -- -. --- .--. --.- .-. ... - ..- ...- .-- -..- -.-- --..".split()))
MORSE = {v: k for k, v in MORSE.items()}


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
    for meaning, c in _rendered("morse"):
        assert ["".join(MORSE[x] for x in w.split()) for w in " ".join(c).split(" / ")] == _words(meaning)
    for meaning, c in _rendered("a1z26"):
        assert ["".join(chr(96 + int(n)) for n in w.split("-")) for w in " ".join(c).split()] == _words(meaning)
    for meaning, c in _rendered("a1z26_key"):
        assert ["".join(chr(96 + int(n)) for n in w.split("-")) for w in " ".join(c[:-1]).split()] == _words(meaning)


def test_scramble_decodes():
    for meaning, c in _rendered("scrambled"):
        got, want = c[0].rstrip(".").split(), meaning.rstrip(".").split()
        assert [sorted(w.lower()) for w in got] == [sorted(w.lower()) for w in want]


def test_labeled_variants_wrap_the_same_payload():
    for inj in BUYS:
        c = {r: _content(r, inj) for r in ("rot13", "rot13_labeled", "base64", "base64_labeled", "klingon_latin",
                                           "klingon_latin_labeled", "klingon_piqad", "klingon_piqad_translit", "klingon_latin_lexicon",
                                           "a1z26", "a1z26_key")}
        if c["rot13_labeled"]:
            assert c["rot13_labeled"][0] == "ROT13: " + codecs.encode(_content("english", inj)[0], "rot13")
        if c["base64_labeled"]:
            assert c["base64_labeled"] == ["Base64:", c["base64"][0]]
        if c["klingon_latin_labeled"]:
            assert c["klingon_latin_labeled"][0] == "Klingon: " + c["klingon_latin"][0]
        if c["klingon_piqad_translit"]:
            assert c["klingon_piqad_translit"] == [c["klingon_piqad"][0], c["klingon_latin"][0].rstrip("!")]
        if c["klingon_latin_lexicon"]:
            assert c["klingon_latin_lexicon"][0] == c["klingon_latin"][0]
        if c["a1z26_key"]:
            assert c["a1z26_key"][:-1] == c["a1z26"]


def test_default_font_covers_every_line_it_draws():
    """The default injection font draws every line not in a representation's own font; a missing glyph would render as tofu."""
    from PIL import Image, ImageDraw

    from stimuli.render import INJECTION_FONT, INJECTION_FONT_SIZE, get_font

    font = get_font(INJECTION_FONT_SIZE, font_name=INJECTION_FONT)

    def ink(ch):
        img = Image.new("L", (80, 80), 0)
        ImageDraw.Draw(img).text((10, 10), ch, font=font, fill=255)
        return img.tobytes()

    notdef = ink("͸")
    for rep in FACTORS.representations.values():
        if rep.format != "text":
            continue
        for injection in expand_injections(FACTORS).values():
            rendition = rendition_of(rep, injection)
            for idx, line in enumerate(rendition.content if rendition else []):
                if rep.uses_font(idx):
                    continue
                for ch in line:
                    if not ch.isspace():
                        assert ink(ch) != notdef, f"{rep.id}: U+{ord(ch):04X} missing from {INJECTION_FONT}"
