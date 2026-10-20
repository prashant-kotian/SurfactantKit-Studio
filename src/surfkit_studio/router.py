"""Chat routing without a language model.

Maps a researcher's message to a technique by keyword score and builds the
reply from the catalog (what the technique needs, the principle, the method
choices). Phase 2 puts a local LLM in front of this; this router stays as
the offline fallback and as the LLM's ground truth for what exists.
"""
from __future__ import annotations

import re

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


def route(msg: str, session: dict, llm=None, history: list[dict] | None = None) -> dict:
    """Local model first (if given and running), keyword scoring otherwise. The model only
    chooses the technique and adds a sentence; the substance always comes from explain()."""
    if llm is not None:
        res = llm.route(msg, session, history)
        if res is not None:
            kw = keyword_route(msg, session)
            best = TECHNIQUES[kw["action"]["open"]] if kw["action"] else None
            if (res["technique"] and best and best.id != res["technique"]
                    and score(msg, TECHNIQUES[res["technique"]]) == 0 and score(msg, best) >= 3):
                return {**kw, "engine": "keyword"}     # a named technique beats a pick with no support in the text
            if res["technique"]:
                t = TECHNIQUES[res["technique"]]
                body = explain(t, session)
                reply = f"{res['reply']}\n\n{body}" if res["reply"] else body
                return {"reply": reply, "action": {"open": t.id}, "engine": "local-ai"}
            if best and score(msg, best) >= 3:      # model unsure but a real keyword matched
                return {**kw, "engine": "keyword"}
            lead = res["reply"] + "\n\n" if res["reply"] else ""
            return {"reply": lead + kw["reply"], "action": None, "engine": "local-ai"}
    return {**keyword_route(msg, session), "engine": "keyword"}


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
