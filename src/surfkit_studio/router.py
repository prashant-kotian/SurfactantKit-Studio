"""Chat routing, with no language model anywhere.

A question about a method, principle or formula is answered from the knowledge base (the
Supporting Information and the Studio's own method notes), quoted, with its source. A message
about the researcher's data is mapped to a technique by keyword score, and the reply is built from
the catalog (what the technique needs, the principle, the method choices).
"""
from __future__ import annotations

import re

from . import knowledge
from .catalog import TECHNIQUES
from .catalog.base import Technique


# title words every surfactant question contains; they say nothing about which analysis is meant
GENERIC = {"surfactant", "surfactants", "micelle", "micelles", "from", "with", "water", "formulation"}


def score(msg: str, t: Technique) -> int:
    m = f" {msg.lower()} "
    s = sum(3 for k in t.keywords if k in m)
    s += sum(1 for w in re.findall(r"[a-z]{4,}", t.title.lower()) if w in m and w not in GENERIC)
    if t.dataset:   # only whole-word aliases of 4+ letters: "c", "st" matched almost any sentence
        s += sum(1 for col in t.dataset.columns for a in col.aliases
                 if len(a.strip()) >= 4 and a.strip() not in GENERIC and re.search(rf"\b{re.escape(a.strip())}\b", m))
    return s


def route(msg: str, session: dict) -> dict:
    """A knowledge question gets the documented answer; data talk opens the matching analysis.
    A question the documentation cannot answer falls through to the analyses when one matches,
    and otherwise says so instead of guessing."""
    if knowledge.is_question(msg):
        ans = knowledge.kb().answer(msg)
        if ans["found"]:
            return {"reply": ans["reply"], "action": ans["action"], "engine": "knowledge"}
        kw = keyword_route(msg, session)
        if kw["action"]:
            return {**kw, "engine": "keyword"}
        return {"reply": ans["reply"], "action": None, "engine": "knowledge"}
    kw = keyword_route(msg, session)
    if kw["action"] is None:
        ans = knowledge.kb().answer(msg)
        if ans["found"]:
            return {"reply": ans["reply"], "action": ans["action"], "engine": "knowledge"}
    return {**kw, "engine": "keyword"}


def keyword_route(msg: str, session: dict) -> dict:
    ranked = sorted(TECHNIQUES.values(), key=lambda t: score(msg, t), reverse=True)
    best = ranked[0]
    if score(msg, best) == 0:
        cats = sorted({t.category for t in TECHNIQUES.values()})
        return {"reply": "I can run these analyses: " + "; ".join(
                    f"{c}: " + ", ".join(t.title for t in TECHNIQUES.values() if t.category == c) for c in cats)
                + ". Tell me what data you have (for example 'surface tension vs concentration') or what you "
                  "want to find (for example 'CMC').",
                "action": None}
    return {"reply": explain(best, session), "action": {"open": best.id}}


def explain(t: Technique, session: dict) -> str:
    parts = [f"{t.title}. {t.summary}"]
    missing = [k for k in t.requires if k not in session]
    if t.dataset:
        cols = " and ".join(f"{c.label} ({'/'.join(c.units)})" for c in t.dataset.columns)
        parts.append(f"I have opened its panel on the right. Upload a CSV or Excel file with {cols}, "
                     f"at least {t.dataset.min_rows} rows; you will confirm the column mapping and units before "
                     f"anything is computed.")
    elif t.level in ("structure", "measurement"):
        what = "the molecule's structure" if t.level == "structure" else "your measured values"
        parts.append(f"I have opened its panel on the right. Enter {what} there; no file is needed.")
    elif missing:
        need = [u.title for u in TECHNIQUES.values() if any(k in u.produces for k in missing)]
        parts.append("This is a derived analysis. It needs a result you have not produced yet"
                     + (f"; run {' or '.join(sorted(set(need)))} first." if need else "."))
    else:
        parts.append("It uses results you already have, so it is ready to run from the panel on the right.")
    if len(t.methods) > 1:
        opts = "\n".join(f"{i}. {m.label}: {m.when}" for i, m in enumerate(t.methods, 1))
        parts.append(f"There is more than one way to do this. Which do you want?\n{opts}\n"
                     "Pick one in the Method box on the right; each shows the principle it works on.")
    elif t.methods:
        parts.append(f"Principle: {t.methods[0].principle}")
    return "\n\n".join(parts)
