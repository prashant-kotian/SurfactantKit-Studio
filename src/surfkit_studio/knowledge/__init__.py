"""Answers to "which formula / principle / method" questions, taken from documents, never generated.

Three sources, all shipped with the Studio:
  si_s1.json  section S1 of the SurfactantKit Supporting Information (exported from the SI source by
              paper3/si/export_studio_kb.py; equations converted from the SI's own LaTeX)
  catalog     the Studio's own method descriptions (catalog/*.py)
  notes.py    how the Studio itself computes things (Workbook mode, definitions, tiers)

Retrieval is BM25 over titles, text and formulas, with domain aliases and tolerance for misspelling.
Below a score threshold the answer is "not in the documentation", never a guess.
"""
from __future__ import annotations

import difflib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ..catalog import TECHNIQUES
from .notes import NOTES

HERE = Path(__file__).parent


@dataclass
class Entry:
    id: str
    title: str
    text: str
    source: str
    kind: str = "description"
    equations: list[str] = field(default_factory=list)
    refs: list[str] = field(default_factory=list)
    technique: str | None = None


STOP = set("a an the of in on at to for from by with and or is are was be been it its this that these those "
           "what which how why when where who do does did can could should would will i me my we our you your "
           "please tell give explain show used use using uses get find there their they them about into than "
           "then also as if not no yes vs versus per".split())
# question words: they say what kind of answer is wanted (see INTENT_*), not what it is about
STOP |= set("formula formulae equation principle method approach technique calculate calculated calculation "
            "compute computed obtain obtained determine determined estimate estimated found expression theory "
            "concept definition define mean meaning value used procedure algorithm way".split())

# names and terms worth matching despite a misspelling ("rubign", "szyszkowsky"); nothing else is
# corrected, so an unrelated word is never bent into a technical one
FUZZY_TARGETS = set("rubingh szyszkowski frumkin langmuir clint rosen gibbs zana tanford griffin davies klevens "
                    "rodenas maeda margules corrin harkins debye henry smoluchowski hueckel ohshima perrin stokes "
                    "einstein ward tordai turro yekta owens wendt kaelble young dupre bikerman nagarajan "
                    "israelachvili micellization counterion solubilization conductivity tensiometry synergism "
                    "aggregation surfactant isotherm adsorption monolayer interfacial electrophoretic "
                    "hydrodynamic coefficient enthalpy entropy".split())
# title words too common to show that a question is about surfactant science
GENERIC_TITLE = set("point model compare all limit data number from curve surface measured series method "
                    "selection analysis value shape size surfactant micelle water formulation mixture solution "
                    "concentration".split())

# phrase -> extra query words (domain vocabulary researchers use for the same thing)
ALIASES = {
    "non linear": "sigmoid nonlinear fit", "nonlinear": "sigmoid fit", "curve fitting": "fit",
    "regular solution": "rubingh beta", "interaction parameter": "beta rubingh", "beta parameter": "beta rubingh",
    "beta m": "rubingh beta", "beta sigma": "rosen monolayer", "beta^sigma": "rosen monolayer",
    "monolayer": "rosen", "synergy": "synergism", "synergistic": "synergism",
    "ideal mixing": "clint", "ideal cmc": "clint", "mixed cmc": "clint rubingh mixed",
    "conductometry": "conductivity", "conductometric": "conductivity", "conductance": "conductivity",
    "tensiometry": "surface tension", "sft": "surface tension", "pendant drop": "surface tension",
    "degree of ionization": "ionization counterion binding", "degree of ionisation": "ionization counterion binding",
    "counter ion": "counterion", "delta g": "free energy", "gibbs energy": "free energy", "enthalpy": "enthalpy van hoff", "vant hoff": "van hoff enthalpy",
    "van't hoff": "van hoff enthalpy", "entropy": "entropy enthalpy van hoff",
    "area per molecule": "amin area", "a min": "amin", "surface excess": "gamma_max excess gibbs",
    "gamma max": "gamma_max excess", "packing parameter": "cpp packing", "aggregation number": "aggregation nagg",
    "quenching": "turro fluorescence aggregation", "light scattering": "debye scattering aggregation",
    "zeta": "zeta electrophoretic", "contact angle": "wetting contact", "surface energy": "owens wetting",
    "cloud point": "cloud", "solubilisation": "solubilization", "msr": "solubilization msr",
    "dynamic surface tension": "dynamic ward tordai", "ward tordai": "ward tordai dynamic",
    "creaming": "emulsion creaming", "ostwald": "ostwald ripening emulsion", "langmuir": "langmuir isotherm",
    "frumkin": "frumkin isotherm", "szyszkowski": "szyszkowski isotherm", "solver": "solver excel",
    "triplicate": "triplicate mean standard deviation", "standard deviation": "mean standard deviation",
    "significant figure": "significant figures", "pc20": "pc20 c20 efficiency", "c20": "c20 pc20",
    "efficiency": "pc20 efficiency", "effectiveness": "effectiveness synergism", "tier": "tier validation",
    "excess free energy": "g^e activity coefficient rubingh", "mixing": "mixed",
    "chain volume": "tanford packing", "chain length": "tanford packing n_c", "tail volume": "tanford packing",
    "debye length": "lambda_d debye screening electrostatic", "screening length": "lambda_d debye",
    "work of adhesion": "w_a young dupre wetting", "spreading coefficient": "spreading wetting",
    "micellar mole fraction": "micellar composition rubingh x1", "micellar composition": "rubingh x1",
    "activity coefficient": "f1 f2 rubingh regular solution",
}

INTENT_FORMULA = re.compile(r"\b(formula|formulae|formulas|equation|equations|expression|calculated|calculate|"
                            r"computed|compute|derive|derived|relation|obtained|determined|estimated|what is the)\b")
INTENT_PRINCIPLE = re.compile(r"\b(principle|theory|concept|basis|meaning|mean|define|definition|why)\b")
INTENT_METHOD = re.compile(r"\b(method|methods|approach|technique|algorithm|procedure|fit|fitting|how is|"
                           r"how do|how does|how are|which)\b")
QUESTION = re.compile(r"\?|\b(formula|equation|principle|theory|method|which|what|how|why|explain|define|"
                      r"definition|meaning|difference|derive|reference|cite)\b")


def _stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def tokens(text: str) -> list[str]:
    t = text.lower().replace("'", "")
    return [_stem(w) for w in re.findall(r"[a-z0-9_^]+", t) if w not in STOP and len(w) > 1]


def _load() -> list[Entry]:
    out: list[Entry] = []
    kb = json.loads((HERE / "si_s1.json").read_text(encoding="utf-8"))
    for sec in kb["sections"]:
        src = f"SurfactantKit Supporting Information, Section {sec['id']} ({sec['title']})"
        cur = None
        for k, it in enumerate(sec["items"]):
            if it["type"] == "p":
                cur = Entry(f"{sec['id']}.{k}", sec["title"], it["text"], src, it["kind"], [], it["refs"])
                out.append(cur)
            elif it["type"] == "eq" and cur is not None:
                cur.equations.append(it["text"])
    for t in TECHNIQUES.values():
        out.append(Entry(f"tech.{t.id}", t.title, t.summary, "SurfactantKit Studio", "technique", technique=t.id))
        for m in t.methods:
            out.append(Entry(f"meth.{t.id}.{m.key}", f"{t.title}: {m.label}",
                             f"{m.principle} When to use it: {m.when}", "SurfactantKit Studio, method description",
                             "method", technique=t.id))
    for i, n in enumerate(NOTES):
        out.append(Entry(f"note.{i}", n["title"], n["text"], "SurfactantKit Studio, how the Studio computes it",
                         "note", list(n["equations"]), list(n["refs"]), n["technique"]))
    return out


class KnowledgeBase:
    K1, B = 1.5, 0.75
    MIN_SCORE = 6.0          # below this nothing in the documentation answers the question

    def __init__(self, entries: list[Entry] | None = None):
        self.entries = entries if entries is not None else _load()
        self.docs = []
        for e in self.entries:
            # equation symbols count twice: a formula question names what the formula contains
            toks = (tokens(e.title) * 2 + tokens(e.text) + tokens(" ".join(e.equations)) * 2
                    + tokens(" ".join(e.refs)))
            self.docs.append(Counter(toks))
        self.N = len(self.docs)
        self.avgdl = sum(sum(d.values()) for d in self.docs) / self.N
        self.df = Counter(w for d in self.docs for w in d)
        # words that show a question is about surfactant science: title words that are not generic,
        # the alias vocabulary, and the reference and technical names
        self.domain = ({w for e in self.entries for w in tokens(e.title)} - GENERIC_TITLE) | FUZZY_TARGETS \
            | {w for v in ALIASES.values() for w in tokens(v)} \
            | {w for e in self.entries for r in e.refs for w in tokens(r) if not w.isdigit()}
        self.domain -= GENERIC_TITLE

    def _expand(self, q: str) -> list[str]:
        low = " " + re.sub(r"[^a-z0-9^' ]+", " ", q.lower()) + " "
        extra = " ".join(v for k, v in ALIASES.items() if f" {k} " in low or (len(k) > 6 and k in low))
        out = []
        for w in tokens(low + " " + extra):
            if w not in self.df and len(w) >= 5:
                near = difflib.get_close_matches(w, FUZZY_TARGETS, n=1, cutoff=0.7)
                if near:
                    w = near[0]
            out.append(w)
        return out

    def _bm25(self, qt: list[str], i: int) -> float:
        d, dl, s = self.docs[i], sum(self.docs[i].values()), 0.0
        for w in set(qt):
            f = d.get(w, 0)
            if not f:
                continue
            idf = math.log(1 + (self.N - self.df[w] + 0.5) / (self.df[w] + 0.5))
            s += idf * f * (self.K1 + 1) / (f + self.K1 * (1 - self.B + self.B * dl / self.avgdl))
        return s

    def search(self, q: str, k: int = 3) -> list[tuple[float, Entry]]:
        qt = self._expand(q)
        if not qt or not (set(qt) & self.domain):
            return []                              # nothing in the question is surfactant science
        low = q.lower()
        f_int, p_int, m_int = INTENT_FORMULA.search(low), INTENT_PRINCIPLE.search(low), INTENT_METHOD.search(low)
        scored = []
        for i, e in enumerate(self.entries):
            s = self._bm25(qt, i)
            if s <= 0:
                continue
            if e.equations:
                s *= 1.6 if f_int else 1.1         # a formula question wants the entry that carries the formula
            elif f_int:
                s *= 0.75
            if p_int and e.kind == "principle":
                s *= 1.15
            if m_int and not f_int and e.kind in ("method", "implementation", "model selection"):
                s *= 1.15
            scored.append((s, e))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]

    def _covers(self, q: str, e_index: int) -> bool:
        """Every topic word of a short question appears in the entry (for one- or two-word questions,
        whose BM25 score stays low even when the match is exact)."""
        qt = set(self._expand(q))
        return 0 < len(qt) <= 2 and qt <= set(self.docs[e_index]) and bool(qt & self.domain)

    def answer(self, q: str) -> dict:
        hits = self.search(q)
        ok = bool(hits) and (hits[0][0] >= self.MIN_SCORE or self._covers(q, self.entries.index(hits[0][1])))
        if not ok:
            near = ", ".join(e.title for _, e in hits[:3]) if hits else ""
            return {"found": False, "reply": "That is not in the SurfactantKit documentation, so I will not guess."
                    + (f" Closest topics: {near}." if near else
                       " Ask about a method, principle or formula, for example: which formula does Rubingh use?"),
                    "action": None}
        s, e = hits[0]
        if INTENT_FORMULA.search(q.lower()) and not e.equations:
            # a formula was asked for: an entry that carries one wins when it is nearly as relevant
            for s2, e2 in hits[1:]:
                if e2.equations and s2 >= 0.85 * s:
                    s, e = s2, e2
                    break
        lines = [f"{e.title}", _brief(e.text)]
        eqs, refs = list(e.equations), list(e.refs)
        for s2, e2 in hits:
            # a near tie in the same SI section: the second paragraph's formulas complete the answer
            if e2 is not e and e2.source == e.source and s2 >= 0.95 * s:
                eqs += [x for x in e2.equations if x not in eqs]
                refs += e2.refs
        if eqs:
            lines.append("Formula: " + "\n         ".join(eqs[:5]))
        if refs:
            lines.append("References: " + "; ".join(dict.fromkeys(refs)))
        lines.append(f"Source: {e.source}.")
        related = [x.title for sc, x in hits[1:] if sc >= 0.6 * s and x.title != e.title]
        if related:
            lines.append("Related: " + "; ".join(dict.fromkeys(related)) + ".")
        return {"found": True, "reply": "\n".join(lines), "entry": e.id,
                "action": {"open": e.technique} if e.technique in TECHNIQUES else None}


def _brief(text: str, limit: int = 480) -> str:
    if len(text) <= limit:
        return text
    out = ""
    for sent in re.split(r"(?<=[.;])\s+", text):
        if out and len(out) + len(sent) > limit:
            break
        out += (" " if out else "") + sent
    return out


def is_question(msg: str) -> bool:
    low = msg.lower()
    data_talk = re.search(r"\b(i have|my data|upload|i measured|here is|attached)\b", low)
    return bool(QUESTION.search(low)) and not (data_talk and not INTENT_FORMULA.search(low))


_KB: KnowledgeBase | None = None


def kb() -> KnowledgeBase:
    global _KB
    if _KB is None:
        _KB = KnowledgeBase()
    return _KB
