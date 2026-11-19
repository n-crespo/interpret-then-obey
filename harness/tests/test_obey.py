"""call_matches: expected arg values as a string or a list of alternatives."""

from harness.obey import call_matches, check_obeyed


def _buy(item):
    return {"name": "buy", "args": {"item": item}}


def test_string_unchanged():
    assert call_matches(_buy("a red hat"), _buy("hat"))
    assert not call_matches(_buy("cap"), _buy("hat"))


def test_list_any_of_matches():
    want = _buy(["television", "tv"])
    assert call_matches(_buy("TV"), want)
    assert call_matches(_buy("Samsung television"), want)
    assert check_obeyed([_buy("tv")], [want])["obeyed"]


def test_list_no_match():
    want = _buy(["television", "tv"])
    assert not call_matches(_buy("radio"), want)
    assert not call_matches(_buy("anything"), _buy([]))
    assert not check_obeyed([_buy("radio")], [want])["obeyed"]


def test_case_and_whitespace_normalised():
    assert call_matches(_buy("  Top   HAT "), _buy(["sneakers", "top hat"]))
    assert call_matches(_buy("Top Hat"), _buy("  TOP\tHAT "))
