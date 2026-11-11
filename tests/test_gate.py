"""API key and Run:AI path prefix on the HTTP server."""
from fastapi.testclient import TestClient

from flide.api.server import create_app


class _Fmt:
    aliases, meta_key, name = (), "flide", "next_token"


class _Eng:
    format = _Fmt()


def test_key_and_prefix(monkeypatch):
    monkeypatch.setenv("FLIDE_API_KEY", "k1")
    monkeypatch.setenv("RUNAI_PATH_PREFIX", "/proj/wl")
    c = TestClient(create_app(_Eng(), "m"))
    assert c.get("/proj/wl/health").status_code == 200          # prefix stripped, health open
    assert c.get("/health").status_code == 200                  # bare path (Run:AI probes) still served
    assert c.get("/proj/wl/v1/models").status_code == 401
    assert c.get("/proj/wl/v1/models", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert c.get("/proj/wl/v1/models", headers={"Authorization": "Bearer k1"}).status_code == 200
    assert c.get("/proj/wlx/v1/models", headers={"Authorization": "Bearer k1"}).status_code == 404  # not our prefix


def test_open_without_key(monkeypatch):
    monkeypatch.delenv("FLIDE_API_KEY", raising=False)
    monkeypatch.delenv("RUNAI_PATH_PREFIX", raising=False)
    assert TestClient(create_app(_Eng(), "m")).get("/v1/models").status_code == 200


def test_metrics_open_and_counted(monkeypatch):
    monkeypatch.setenv("FLIDE_API_KEY", "k1")
    monkeypatch.setenv("RUNAI_PATH_PREFIX", "/proj/wl")
    c = TestClient(create_app(_Eng(), "m"))
    before = c.get("/metrics").text                              # open, like SGLang's /metrics
    c.post("/proj/wl/v1/systemone", content=b"{", headers={"Authorization": "Bearer k1"})  # 422
    after = c.get("/metrics")
    assert after.status_code == 200 and before != after.text   # a 422 is not a finished request ...
    assert 'sglang:num_requests_total{model_name="m"} 0' in after.text
    assert 'sglang:num_running_reqs{model_name="m"} 0' in after.text  # ... and leaves nothing running
