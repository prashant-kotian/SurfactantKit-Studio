"""Technique registry: every technique the app offers, and the flow tree.

The tree is derived, not hand-drawn: a technique's children are the ones
listed in its `unlocks`. Primary techniques (run from raw data) are roots.
"""
from __future__ import annotations

from surfactantkit.validation_tiers import get_tool_tier, VALIDATION_TIERS

from . import aggregation, mixtures, tensiometry, thermo
from .base import Technique

TECHNIQUES: dict[str, Technique] = {t.id: t for t in [*tensiometry.TECHNIQUES, *thermo.TECHNIQUES,
                                                      *mixtures.TECHNIQUES, *aggregation.TECHNIQUES]}

TIER_MEANING = {
    "T1": "Reproduces published numbers from primary literature.",
    "T1†": "Reproduces published numbers, with a documented qualification.",
    "T2": "Equation checked against its source; no published worked number to match, validated by "
          "round-trip and limiting cases.",
    "T3": "Estimate by construction; not a literature value.",
}


EXACT = {   # pure arithmetic: nothing to validate beyond the formula itself
    "cmc_to_mole_fraction": "Exact unit conversion: X = c / (c + 55.5 mol/L).",
    "counterion_binding_degree": "Exact formula beta = 1 - S2/S1; accuracy follows the conductivity fit.",
}


def tiers(t: Technique) -> list[dict]:
    out = []
    for name in t.tools:
        tier = get_tool_tier(name)
        if tier is None and name in EXACT:
            out.append({"tool": name, "tier": "exact", "meaning": EXACT[name], "evidence": EXACT[name]})
            continue
        if tier is None:
            out.append({"tool": name, "tier": "not rated",
                        "meaning": "No validation tier recorded in SurfactantKit yet; treat as an unvalidated "
                                   "cross-check.", "evidence": ""})
            continue
        ev = next((v["evidence"] for k, v in VALIDATION_TIERS.items() if k == name), "")
        out.append({"tool": name, "tier": tier, "meaning": TIER_MEANING.get(tier, tier), "evidence": ev})
    return out


def tree() -> list[dict]:
    """Categories -> primary techniques -> what each unlocks (recursively, no repeats)."""
    cats: dict[str, list] = {}
    for t in TECHNIQUES.values():
        cats.setdefault(t.category, [])

    def node(t: Technique, seen: set) -> dict:
        seen = seen | {t.id}
        return {"id": t.id, "title": t.title, "level": t.level,
                "children": [node(TECHNIQUES[u], seen) for u in t.unlocks if u in TECHNIQUES and u not in seen]}

    for t in TECHNIQUES.values():
        cats[t.category].append({"id": t.id, "title": t.title, "level": t.level,
                                 "unlocks": [node(TECHNIQUES[u], {t.id}) for u in t.unlocks if u in TECHNIQUES]})
    return [{"category": c, "techniques": sorted(v, key=lambda x: x["level"] != "primary")} for c, v in cats.items()]
