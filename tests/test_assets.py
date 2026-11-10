"""System One `assets` (MISA SGLang fork format): references in the state become images in place."""
import pytest

from flide.api.schema import SystemOneRequest
from flide.formats.next_token import ASSET, _image_url, _parts, bind_assets

PNG = "iVBORw0KGgo="


def req(state, questions=None, **kw):
    return SystemOneRequest.model_validate({"state": state, "questions": questions or {
        "q": {"type": "noul", "instructions": "Is it a cat?"}}, **kw})


def test_state_references_become_marks_in_order():
    r = req({"note": "first img_a then img_b, again img_a", "pic": "img_b"},
            assets={"img_a": {"type": "image", "format": "png", "data_base64": PNG},
                    "img_b": {"format": "jpg", "data_base64": PNG}})
    state, urls = bind_assets(r)
    assert state == {"note": f"first {ASSET} then {ASSET}, again {ASSET}", "pic": ASSET}
    assert urls == [f"data:image/png;base64,{PNG}", f"data:image/jpeg;base64,{PNG}",
                    f"data:image/png;base64,{PNG}", f"data:image/jpeg;base64,{PNG}"]


def test_longer_reference_wins():
    state, urls = bind_assets(req("see img_10 img_1", assets={
        "img_1": {"format": "png", "data_base64": PNG}, "img_10": {"format": "jpeg", "data_base64": PNG}}))
    assert state == f"see {ASSET} {ASSET}" and urls[0].startswith("data:image/jpeg")


@pytest.mark.parametrize("assets,questions,msg", [
    ({"a1": {"format": "gif", "data_base64": PNG}}, None, "format"),
    ({"a1": {"format": "png", "data_base64": "not base64!"}}, None, "base64"),
    ({"a1": {"format": "png", "part": "f"}}, None, "multipart"),
    ({"zz": {"format": "png", "data_base64": PNG}}, None, "not referenced"),
    ({"a1": {"format": "png", "data_base64": PNG}}, {"q": {"type": "noul", "instructions": "is a1 red?"}}, "state only"),
])
def test_refused(assets, questions, msg):
    with pytest.raises(ValueError, match=msg):
        bind_assets(req("photo a1", questions, assets=assets))


def test_parts_and_image_url():
    assert _parts(f"x{ASSET}y{ASSET}") == [{"type": "text", "text": "x"}, {"type": "image"},
                                           {"type": "text", "text": "y"}, {"type": "image"}]
    assert _image_url({"type": "image_url", "image_url": {"url": "data:x"}}) == "data:x"
    assert _image_url({"url": "data:y"}) == "data:y" and _image_url("abc") == "abc"
