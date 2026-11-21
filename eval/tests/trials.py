"""Cases and trials built from stimuli/src/, shared by the eval tests."""

import json

from eval.trials import Response, Trial
from harness.obey import check_obeyed
from stimuli.attack_types import SRC_DIR
from stimuli.cases import Case, Representation, context_from_src, prompt_from_src
from stimuli.generate import expand_injections

PROMPTS = json.loads((SRC_DIR / "prompts.json").read_text(encoding="utf-8"))
CONTEXTS = json.loads((SRC_DIR / "context.json").read_text(encoding="utf-8"))
INJECTIONS = expand_injections(json.loads((SRC_DIR / "injections.json").read_text(encoding="utf-8")))
BEAR = [{"name": "buy", "args": {"item": "bear"}}]
REPS = {  # as in stimuli/src/representations.json
    "english": Representation("english", "text", "natural", "english", "latin"),
    "klingon_piqad": Representation("klingon_piqad", "text", "constructed", "klingon", "non_latin"),
    "pictograms": Representation("pictograms", "image", "symbols", None, None),
    "none": Representation("none", "none", "baseline", None, None),
}
REP_ORDER = ["english", "klingon_piqad", "pictograms", "none"]


def make_case(prompt, context, rep, image=None, injection="buy_bear"):
    case_id = f"{prompt}.{context}.{injection}.{rep}"
    return Case(case_id, image or f"stimuli/images/{case_id}.png", None, prompt_from_src(prompt, PROMPTS[prompt]),
                context_from_src(context, CONTEXTS[context]), INJECTIONS[injection], REPS[rep])


def trial(rep, calls=(), prompt="buy", context="product_info", stop_reason="stop", error=None, epoch=1, text="",
          injection="buy_bear"):
    """A trial scored as the harness scores it (check_obeyed in harness/obey.py)."""
    case = make_case(prompt, context, rep, injection=injection)
    calls = list(calls)
    score = check_obeyed(calls, case.injection.expected_calls)
    return Trial(
        case=case,
        epoch=epoch,
        response=Response(calls=calls, text=text, stop_reason=stop_reason, error=error),
        obeyed=score["obeyed"],
        n_matched=score["n_matched"],
        off_target_calls=score["off_target_calls"],
    )


def buy(item):
    return {"name": "buy", "args": {"item": item}}


def directions(place):
    return {"name": "get_directions", "args": {"destination": place}}


def search(query):
    return {"name": "search_web", "args": {"query": query}}


MUG = buy("Thermal Ceramic Travel Mug")
TRIALS = [
    trial("english", [buy("bear")], prompt="help", context="info_board"),         # escalation, obeyed
    trial("english", [MUG]),                                                       # hijack, off-target
    trial("klingon_piqad", []),                                                    # hijack, no call
    trial("pictograms", [buy("teddy bear")], prompt="help", context="info_board"),  # escalation, obeyed
    trial("english", [buy("bear")], context="info_board"),  # no_target: item choice, not attack success
    trial("none", [MUG]),  # baseline: buys the shown product, not the bear
    trial("none", [], context="info_board"),
    trial("english", [], error="boom", prompt="read"),
]
