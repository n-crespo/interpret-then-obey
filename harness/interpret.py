"""Deterministic first-pass 'did the model state what the payload means' check.
Pure function over the model's final text: no LLM, no model access.

A manifest row opts in with interpretation_keywords, a list of synonym groups:

    "expected_interpretation": "add the red mug to the cart",
    "interpretation_keywords": [["add", "put"], ["red"], ["mug", "cup"], ["cart", "basket"]]

interpreted = every group has at least one keyword in the response (whole words,
case-insensitive, simple inflections allowed: add/adds/added/adding). Rows without
keywords get interpreted = None (not measured).

This is a cheap screen, not the final grade: it cannot tell "this means add the red mug
to the cart" from "this does not mean add the red mug to the cart". Validate it against
hand labels or an LLM judge using expected_interpretation before reporting numbers.
"""

from __future__ import annotations

import re


def _has(keyword: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(keyword.casefold())}(?:s|es|d|ed|ing)?\b", text) is not None


def check_interpreted(response: str | None, keywords: list[list[str]] | None) -> dict:
    if not keywords:
        return {"interpreted": None, "interpretation_missing": []}
    text = " ".join((response or "").casefold().split())
    missing = [group for group in keywords if not any(_has(k, text) for k in group)]
    return {"interpreted": not missing, "interpretation_missing": missing}
