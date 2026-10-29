"""Knowledge base: the documented answers, their formulas, and the refusal of everything else."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest
from surfactantkit import mixed_micelle as mm

from kb_questions import IN_SCOPE, OUT_OF_SCOPE
from surfkit_studio import knowledge, router
from surfkit_studio.catalog import TECHNIQUES
from surfkit_studio.knowledge.notes import NOTES

KB_FILE = Path(knowledge.__file__).parent / "si_s1.json"


def _norm(s: str) -> str:
    return s.lower().replace(" ", "")


def test_every_researcher_question_gets_the_right_formula_or_topic():
    K = knowledge.kb()
    misses = [q for q, must in IN_SCOPE if not (K.answer(q)["found"] and _norm(must) in _norm(K.answer(q)["reply"]))]
    assert misses == []


def test_off_topic_questions_are_refused_not_guessed():
    K = knowledge.kb()
    answered = [q for q in OUT_OF_SCOPE if K.answer(q)["found"]]
    assert answered == []
    assert "not in the SurfactantKit documentation" in K.answer(OUT_OF_SCOPE[0])["reply"]


def test_si_export_is_complete_and_keyboard_only():
    kb = json.loads(KB_FILE.read_text(encoding="utf-8"))
    assert len(kb["sections"]) == 15 and kb["sections"][0]["id"] == "S1.1"
    eqs = [i["text"] for s in kb["sections"] for i in s["items"] if i["type"] == "eq"]
    assert len(eqs) == 50
    texts = eqs + [i["text"] for s in kb["sections"] for i in s["items"] if i["type"] == "p"]
    texts += [e for n in NOTES for e in n["equations"]] + [n["text"] for n in NOTES]
    assert all(re.fullmatch(r"[ -~]*", t) for t in texts)          # printable ASCII only


def test_every_technique_has_an_entry_and_notes_point_at_real_techniques():
    ids = {e.id for e in knowledge.kb().entries}
    assert {f"tech.{t}" for t in TECHNIQUES} <= ids
    assert all(n["technique"] in TECHNIQUES for n in NOTES if n["technique"])


# --- the converted formulas mean what the toolkit computes ------------------------------------
def _py(expr: str) -> str:
    """Keyboard formula text -> Python: ln -> log, ^ -> **, [ ] -> ( ), spaces between symbols -> *."""
    s = re.sub(r"\b(ln|exp|sqrt)\s+(?=[(\[])", r"\1", expr)
    s = s.replace("[", "(").replace("]", ")").replace("^", "**")
    s = re.sub(r"\bln\b", "log", s)
    s = re.sub(r"(?<=[\w)])\s+(?=[\w(])", "*", s)
    s = re.sub(r"\b(?!log\b|exp\b|sqrt\b)([A-Za-z_]\w*)\(", r"\1*(", s)     # beta(1-x1) is a product
    return s


def _eval(expr: str, **v) -> float:
    return eval(_py(expr), {"log": math.log, "exp": math.exp, "sqrt": math.sqrt}, v)  # noqa: S307 - test-only


def _eq(key: str) -> str:
    kb = json.loads(KB_FILE.read_text(encoding="utf-8"))
    return next(i["text"] for s in kb["sections"] for i in s["items"] if i["type"] == "eq" and i["key"] == key)


def test_converted_rubingh_and_clint_formulas_evaluate_to_the_toolkit_values():
    a, c1, c2, c12 = 0.4, 8.0, 1.0, 1.2
    x1 = mm.solve_rubingh_x(a, c12, c1, c2)
    v = dict(alpha1=a, CMC1=c1, CMC2=c2, CMC12=c12, x1=x1)
    mass_balance, beta = _eq("rubingh").split("; ")
    lhs, rhs = mass_balance.split(" = ")
    assert _eval(lhs, **v) == pytest.approx(_eval(rhs, **v), rel=1e-9)
    assert _eval(beta.split(" = ")[1], **v) == pytest.approx(mm.rubingh_beta(x1, a, c12, c1), rel=1e-12)
    clint = _eq("clint").split("; ")[0].split(" = ")[1]            # alpha1/CMC1 + (1-alpha1)/CMC2 = 1/CMC12
    assert 1 / _eval(clint, **v) == pytest.approx(mm.clint_ideal_cmc(a, c1, c2), rel=1e-12)
    f1, f2 = mm.activity_coefficients(x1, -2.0)
    rst = _eq("rst").split(", ")
    assert _eval(rst[0].split(" = ")[1], beta=-2.0, x1=x1) == pytest.approx(f1, rel=1e-12)
    assert _eval(rst[1].split(" = ")[1], beta=-2.0, x1=x1) == pytest.approx(f2, rel=1e-12)


def test_note_formulas_for_the_solver_sheets_match_the_si_formulas():
    a, c1, c2, c12 = 0.3, 8.0, 0.05, 0.06
    x1 = mm.solve_rubingh_x(a, c12, c1, c2)
    v = dict(alpha1=a, CMC1=c1, CMC2=c2, CMC12=c12, x1=x1)
    note = next(n for n in NOTES if n["title"].startswith("Rubingh beta^M at each composition"))
    f1, f2 = (part.split(" = ")[1] for part in note["equations"][0].split("; "))
    assert _eval(f1, **v) == pytest.approx(_eval(f2, **v), rel=1e-9)            # F1 - F2 = 0 at the root
    assert _eval(note["equations"][1].split(" = ")[1], **v) == pytest.approx(mm.rubingh_beta(x1, a, c12, c1))


# --- chat routing ---------------------------------------------------------------------------
def test_a_formula_question_is_answered_from_the_documentation():
    r = router.route("which formula does Rubingh use?", {})
    assert r["engine"] == "knowledge" and "ln" in r["reply"] and "Source:" in r["reply"]


def test_data_talk_still_opens_the_analysis():
    r = router.route("I have surface tension vs concentration data and want the CMC", {})
    assert r["engine"] == "keyword" and r["action"] == {"open": "cmc_tensiometry"}


def test_generic_words_alone_route_nowhere():
    r = router.route("surfactant micelle water formulation", {})
    assert r["action"] is None


def test_unanswerable_question_says_so():
    r = router.route("what is the capital of France?", {})
    assert r["action"] is None and "not in the SurfactantKit documentation" in r["reply"]
