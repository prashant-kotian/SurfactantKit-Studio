"""Optional literature search: off by default, only typed keywords can leave, numbers lists refused."""
import os

import pytest
from fastapi.testclient import TestClient

from surfkit_studio import literature
from surfkit_studio.app import app

client = TestClient(app)


def _sid(web=False):
    sid = client.post("/api/session").json()["sid"]
    client.post("/api/settings", json={"sid": sid, "use_ai": False, "web_search": web})
    return sid


def test_trigger_parsing():
    assert literature.wants_search("search: gemini surfactant CMC") == "gemini surfactant CMC"
    assert literature.wants_search("Find papers on zeta potential of micelles") == "zeta potential of micelles"
    assert literature.wants_search("I have surface tension data") is None
    assert literature.wants_search("search:") is None


def test_pasted_data_is_refused_before_anything_is_sent():
    with pytest.raises(literature.QueryRefused, match="numbers"):
        literature.check_query("0.41 69.9 0.81 67.9 1.62 62.9 3.25 54.6")
    with pytest.raises(literature.QueryRefused):
        literature.check_query("x" * 300)
    assert literature.check_query("  CTAB   CMC 25 C  ") == "CTAB CMC 25 C"


def test_search_is_off_by_default_and_sends_nothing(monkeypatch):
    called = []
    monkeypatch.setattr(literature, "search", lambda q, n=5: called.append(q))
    sid = client.post("/api/session").json()["sid"]
    r = client.post("/api/chat", json={"sid": sid, "message": "search: gemini surfactant"}).json()
    assert "nothing was sent" in r["reply"] and not called
    assert client.post("/api/search", json={"sid": sid, "query": "gemini"}).status_code == 403


def test_search_on_shows_exactly_what_was_sent(monkeypatch):
    fake = {"query_sent": "gemini surfactant", "source": "OpenAlex",
            "results": [{"title": "A paper", "year": 2019, "authors": ["A. Author"], "more_authors": True,
                         "venue": "Colloids Surf. A", "doi": "10.1/x"}]}
    monkeypatch.setattr(literature, "search", lambda q, n=5: fake)
    sid = _sid(web=True)
    r = client.post("/api/chat", json={"sid": sid, "message": "search: gemini surfactant"}).json()
    assert r["engine"] == "literature" and '"gemini surfactant"' in r["reply"]
    assert "not checked citations" in r["reply"] and "doi:10.1/x" in r["reply"]


def test_toggles_are_independent():
    sid = client.post("/api/session").json()["sid"]
    s = client.post("/api/settings", json={"sid": sid, "web_search": True}).json()
    assert s["web_search"] is True and s["use_ai"] is True
    s = client.post("/api/settings", json={"sid": sid, "use_ai": False}).json()
    assert s["web_search"] is True and s["use_ai"] is False


@pytest.mark.skipif(not os.environ.get("SURFKIT_LIVE"), reason="live network test; set SURFKIT_LIVE=1")
def test_live_search_returns_records():
    res = literature.search("gemini surfactant critical micelle concentration", n=3)
    assert res["results"] and res["results"][0]["title"]
