"""System One `assets` (MISA SGLang fork format): references become images where they appear."""
import pytest

from flide.api.schema import SystemOneRequest
from flide.formats.next_token import (ASSET_MARK, CLOSE, OPEN, _image_url, _parts, asset_questions, bind_assets,
                                      split_by_assets)

PNG = "iVBORw0KGgo="
A = {"format": "png", "data_base64": PNG}


def req(state, questions=None, **kw):
    return SystemOneRequest.model_validate({"state": state, "questions": questions or {
        "q": {"type": "noul", "instructions": "Is it a cat?"}}, **kw})


def m(i):
    return f"{OPEN}{i}{CLOSE}"


def test_state_references_become_marks():
    r = req({"note": "first img_a then img_b, again img_a", "pic": "img_b"},
            assets={"img_a": {"type": "image", **A}, "img_b": {"format": "jpg", "data_base64": PNG}})
    state, questions, urls = bind_assets(r)
    assert state == {"note": f"first {m(0)} then {m(1)}, again {m(0)}", "pic": m(1)}
    assert urls == [f"data:image/png;base64,{PNG}", f"data:image/jpeg;base64,{PNG}"]
    assert asset_questions(r) == [] and split_by_assets(r) is None


def test_longer_reference_wins():
    state, _, urls = bind_assets(req("see img_10 img_1", assets={"img_1": A, "img_10": {"format": "jpeg",
                                                                                       "data_base64": PNG}}))
    assert state == f"see {m(1)} {m(0)}"


def test_question_assets_are_marked_and_split():
    r = req({"query": "a1-query"}, {
        "rest": {"type": "noul", "instructions": "Is the query a shoe?"},
        "u1": {"type": "noul", "instructions": "Do a1-query and b2-cand show one product?"},
        "pick": {"type": "choice", "instructions": "Which matches?", "criteria": {"c1": "b2-cand", "none": "No"}}},
        assets={"a1-query": A, "b2-cand": A})
    _, questions, _ = bind_assets(r)
    assert questions["u1"].instructions == f"Do {m(0)} and {m(1)} show one product?"
    assert questions["pick"].criteria == {"c1": m(1), "none": "No"}
    assert asset_questions(r) == ["u1", "pick"]
    parts = split_by_assets(r)
    assert [list(p.questions) for p in parts] == [["rest"], ["u1"], ["pick"]]
    assert [list(p.assets) for p in parts] == [["a1-query"], ["a1-query", "b2-cand"], ["a1-query", "b2-cand"]]
    one = req("x", {"u1": {"type": "noul", "instructions": "a1-query?"}}, assets={"a1-query": A})
    assert split_by_assets(one) is None and asset_questions(one) == ["u1"]


@pytest.mark.parametrize("assets,msg", [
    ({"a1": {"format": "gif", "data_base64": PNG}}, "format"),
    ({"a1": {"format": "png", "data_base64": "not base64!"}}, "base64"),
    ({"a1": {"format": "png", "part": "f"}}, "multipart"),
    ({"a1": A, "zz": A}, "not referenced"),
])
def test_refused(assets, msg):
    with pytest.raises(ValueError, match=msg):
        bind_assets(req("photo a1", assets=assets))


def test_parts_and_image_url():
    assert _parts(f"x{m(0)}y{m(12)}") == [{"type": "text", "text": "x"}, {"type": "image"},
                                         {"type": "text", "text": "y"}, {"type": "image"}]
    assert ASSET_MARK.findall(f"{m(3)} {m(0)}") == ["3", "0"]
    assert _image_url({"type": "image_url", "image_url": {"url": "data:x"}}) == "data:x"
    assert _image_url({"url": "data:y"}) == "data:y" and _image_url("abc") == "abc"
