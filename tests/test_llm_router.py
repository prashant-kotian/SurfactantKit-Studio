"""Local-model routing logic with a fake model (no Ollama needed)."""
from surfkit_studio import llm, router


class FakeLLM:
    def __init__(self, out):
        self.out = out

    def route(self, message, session, history=None):
        return llm.sanitize(self.out) if self.out is not None else None


def test_model_choice_opens_panel_and_catalog_text_is_appended():
    r = router.route("my curve", {}, FakeLLM({"technique": "cmc_tensiometry", "intent": "run",
                                               "reply": "Sure, let us find your CMC."}))
    assert r["action"] == {"open": "cmc_tensiometry"} and r["engine"] == "local-ai"
    assert r["reply"].startswith("Sure, let us find your CMC.")
    assert "Which do you want?" in r["reply"]                 # method choices come from the catalog


def test_reply_with_a_number_or_citation_is_dropped():
    for bad in ("Your CMC is 8.2 mM.", "As Zana et al. showed", "see doi:10.1021/x", "(2019) says"):
        out = llm.sanitize({"technique": "cmc_tensiometry", "intent": "run", "reply": bad})
        assert out["reply"] == ""


def test_unknown_technique_is_rejected():
    assert llm.sanitize({"technique": "make_coffee", "intent": "run", "reply": "ok"})["technique"] is None


def test_model_unsure_falls_back_to_clear_keywords():
    r = router.route("conductivity data, counterion binding?", {},
                     FakeLLM({"technique": None, "intent": "other", "reply": "Hmm."}))
    assert r["action"] == {"open": "cmc_conductivity"} and r["engine"] == "keyword"


def test_off_topic_message_opens_nothing_even_when_model_unsure():
    for msg in ("how do I make a cake", "translate this to French", "what can this app do"):
        r = router.route(msg, {}, FakeLLM({"technique": None, "intent": "other", "reply": "I can help with surfactant data."}))
        assert r["action"] is None, msg
        assert router.keyword_route(msg, {})["action"] is None, msg


def test_model_down_uses_keyword_router():
    r = router.route("surface tension vs concentration, CMC please", {}, FakeLLM(None))
    assert r["engine"] == "keyword" and r["action"] == {"open": "cmc_tensiometry"}


def test_system_prompt_lists_every_technique_and_forbids_numbers():
    p = llm.system_prompt({})
    from surfkit_studio.catalog import TECHNIQUES
    assert all(tid in p for tid in TECHNIQUES)
    assert "never write any number" in p
