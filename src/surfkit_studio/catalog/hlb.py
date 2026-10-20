"""HLB from molecular structure (no measured curve needed).

Griffin (mass of the hydrophilic part), Davies (group numbers; refuses groups
it has no verified number for) and the Guo-Rong-Ying effective-chain-length
refinement for alcohol ethoxylates.
"""
from __future__ import annotations

import re

from surfactantkit import hlb as H

from .base import Method, Param, RunInput, RunResult, Technique, Value

RANGES = [  # Griffin's application ranges (Griffin 1949)
    (3, 6, "water-in-oil emulsifier"), (7, 9, "wetting agent"), (8, 16, "oil-in-water emulsifier"),
    (13, 16, "detergent"), (15, 18, "solubilizer"),
]


def _uses(h: float) -> list[str]:
    return [name for lo, hi, name in RANGES if lo <= h <= hi]


def _groups(text: str) -> dict[str, int]:
    out = {}
    for part in re.split(r"[,;]\s*", text.strip()):
        if not part:
            continue
        m = re.fullmatch(r"\s*([A-Za-z0-9_()+\-]+)\s*[:=x*]\s*(\d+)\s*", part)
        if not m:
            raise ValueError(f"Could not read group '{part}'. Use the form  SO4Na: 1, CH2: 11, CH3: 1")
        out[m.group(1)] = out.get(m.group(1), 0) + int(m.group(2))
    return out


def run_hlb(inp: RunInput) -> RunResult:
    p, method = inp.params, inp.method or "griffin"
    if method == "griffin":
        mh, mt = float(p["mw_hydrophilic"]), float(p["mw_total"])
        if not 0 < mh < mt:
            raise ValueError("The hydrophilic mass must be positive and smaller than the total molar mass.")
        h, calls = H.hlb_griffin(mh, mt), ["hlb.hlb_griffin"]
        basis = "Griffin: HLB = 20 x (hydrophilic molar mass / total molar mass)."
    elif method == "davies":
        groups = _groups(str(p.get("groups") or ""))
        try:
            h = H.hlb_davies(groups)
        except KeyError as e:
            known = ", ".join(sorted({*H.DAVIES_HYDROPHILIC_GROUPS, *H.DAVIES_LIPOPHILIC_GROUPS}))
            raise ValueError(f"No verified Davies group number for {e}. Known groups: {known}. "
                             "The Davies method is not applied with guessed group numbers.")
        calls = ["hlb.hlb_davies"]
        basis = "Davies: HLB = 7 + sum(hydrophilic group numbers) - sum(lipophilic group numbers)."
    elif method == "guo":
        if H.DAVIES_HYDROPHILIC_GROUPS.get("EO_unit") != 0.33:
            raise ValueError("This SurfactantKit version predates the EO-weight fix (2026-10-20); "
                             "the Guo method is disabled to avoid wrong HLB values. Update SurfactantKit.")
        n_c, n_eo = int(float(p["n_carbons"])), int(float(p["n_eo"]))
        h = H.hlb_davies_guo_ecl(n_c, n_eo, extra_group_counts={"OH_free": 1})
        calls = ["hlb.hlb_davies_guo_ecl(extra_group_counts={'OH_free': 1})"]
        basis = "Guo-Rong-Ying: Davies group numbers on effective EO and CH2 chain lengths, terminal OH included."
    else:
        raise ValueError(f"Unknown HLB method {method!r}.")
    uses = _uses(h)
    concl = [f"HLB = {h:.1f}. " + (f"In Griffin's classification this suits use as: {', '.join(uses)}."
                                   if uses else "This lies outside Griffin's usual application ranges.")]
    concl.append("HLB values from different methods are not interchangeable; quote the method with the number.")
    warn = []
    if method == "griffin" and not str(p.get("ionic", "")).lower() in ("", "no", "false"):
        warn.append("Griffin's mass-fraction method was devised for nonionic surfactants; for ionic surfactants "
                    "prefer Davies group numbers.")
    return RunResult([Value("HLB", h, sig=3), Value("Method", basis),
                      Value("Typical uses (Griffin ranges)", ", ".join(uses) or "none")],
                     [], concl, warn, {"hlb": h}, calls)


HLB = Technique(
    id="hlb", category="Formulation", title="HLB (hydrophilic-lipophilic balance)", level="structure",
    summary="HLB from the molecular structure by Griffin, Davies or the Guo-Rong-Ying method, with Griffin's "
            "application ranges (emulsifier, wetting agent, detergent, solubilizer).",
    params=[Param("mw_hydrophilic", "Griffin: molar mass of the hydrophilic part", "float", "g/mol", None, required=False),
            Param("mw_total", "Griffin: total molar mass", "float", "g/mol", None, required=False),
            Param("groups", "Davies: group counts", "text", "", "", required=False,
                  help="e.g. SO4Na: 1, CH2: 11, CH3: 1"),
            Param("n_carbons", "Guo: carbons in the alkyl chain (n of CnEm)", "float", "", None, required=False),
            Param("n_eo", "Guo: ethylene oxide units (m of CnEm)", "float", "", None, required=False)],
    methods=[Method("griffin", "Griffin (mass fraction)",
                    "HLB = 20 x hydrophilic mass fraction; simple and standard for nonionic surfactants.",
                    "Nonionic surfactants where the hydrophilic block is well defined (e.g. EO chain)."),
             Method("davies", "Davies (group numbers)",
                    "Adds tabulated group numbers; works for ionic head groups. Unknown groups are refused, not "
                    "guessed.", "Ionic surfactants or when the structure is known group by group."),
             Method("guo", "Guo-Rong-Ying (alcohol ethoxylates CnEm)",
                    "Davies group numbers applied to effective EO and CH2 chain lengths, correcting Davies for "
                    "long EO chains; the terminal OH of CnEm is included.",
                    "Fatty alcohol ethoxylates. Needs SurfactantKit with the 2026-10-20 EO-weight fix.")],
    run=run_hlb, tools=["hlb_griffin", "hlb_davies", "hlb_davies_guo_ecl"],
    citations=["griffin_1949", "davies_1957", "guo_2006"],
    followups=["Match the HLB to the required HLB of your oil phase to choose an emulsifier.",
               "For ionic surfactants and salinity effects, HLD is the more predictive formulation descriptor."],
    keywords=["hlb", "hydrophilic lipophilic", "hydrophile", "emulsifier", "griffin", "davies", "ethoxylate"],
)

TECHNIQUES = [HLB]
