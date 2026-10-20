"""Hydrophilic-lipophilic difference (HLD).

Primary: a salinity scan (optimal salinity S* for several oils of known
EACN) gives the surfactant's characteristic curvature Cc and the EACN
coefficient k. Measurement-level: HLD of one surfactant/oil/brine
formulation and its optimal salinity, from Cc and k (fitted, entered, or the
cationic quaternary ammonium values published by Schirone et al. 2021).
"""
from __future__ import annotations

import math

from surfactantkit import hld as H

from .. import plotting as P
from .base import Column, DatasetSpec, Figure, Method, Param, RunInput, RunResult, Technique, Value

SCAN = DatasetSpec(
    columns=[Column("eacn", "Oil EACN", ["-"], ["eacn", "alkane", "acn", "oil"]),
             Column("s_star", "Optimal salinity S*", ["g/100 mL"], ["s*", "optimal", "salinity", "nacl"])],
    min_rows=3, example="synthetic_salinity_scan.csv")

PRESETS = [("", "None (enter Cc and k)")] + [
    (name, f"{name} (Cc {cc:g}, k {H.CATIONIC_QUAT_K:g})") for name, (cc, _) in H.CATIONIC_QUAT_CC.items()]


def _delta_t(p: dict) -> float:
    return float(p.get("temperature_K") or 298.15) - 298.15


# ------------------------------------------------------------ salinity scan
def run_scan(inp: RunInput) -> RunResult:
    x, s = inp.data["eacn"], inp.data["s_star"]
    p = inp.params
    alpha = float(p.get("alpha") if p.get("alpha") not in (None, "") else H.ALPHA_IONIC_DEFAULT)
    dT = _delta_t(p)
    r = H.fit_k_and_cc_from_salinity_scan(x, s, alpha, dT)
    fig, ax = P.new()
    ax.scatter(x, r.ln_s_star_used, s=20, color=P.DATA, zorder=3, label="ln S*")
    xl = [min(x), max(x)]
    ax.plot(xl, [r.k * v + alpha * dT - r.cc for v in xl], color=P.FIT, lw=1.5, label="Fit: ln S* = k EACN - Cc")
    ax.set_xlabel("Oil EACN"); ax.set_ylabel("ln S*  (S* in g/100 mL)"); ax.legend(fontsize=7, loc="best")
    warn = ["The fit uses the ionic-surfactant HLD form (ln S). For ethoxylated nonionics salinity enters linearly; "
            "use the HLD calculator with the nonionic form instead."]
    if r.n_points < 4:
        warn.append(f"Only {r.n_points} oils: k and Cc rest on very few points; three is the minimum, four or more "
                    "make the R^2 meaningful.")
    concl = [f"Characteristic curvature Cc = {r.cc:.3g} and EACN coefficient k = {r.k:.3g} (R^2 {r.r_squared:.3f}).",
             ("Cc is negative: on its own the surfactant is hydrophilic and needs salt or a more lipophilic oil to "
              "reach the balanced (Winsor III) state." if r.cc < 0 else
              "Cc is positive: on its own the surfactant is lipophilic and balances with little salt.")]
    return RunResult([Value("Characteristic curvature Cc", r.cc, sig=3), Value("EACN coefficient k", r.k, sig=3),
                      Value("R^2 of ln S* against EACN", r.r_squared, sig=3), Value("Oils in the scan", r.n_points)],
                     [Figure("scan", P.to_png(fig), "Logarithm of the optimal salinity against oil EACN.")],
                     concl, warn, {"hld_cc": r.cc, "hld_k": r.k}, ["hld.fit_k_and_cc_from_salinity_scan"])


SCAN_T = Technique(
    id="hld_scan", category="Formulation", title="HLD salinity scan: Cc and k", level="primary",
    summary="Characteristic curvature Cc and EACN coefficient k of an ionic surfactant from the optimal salinity "
            "measured with several oils.",
    dataset=SCAN,
    params=[Param("temperature_K", "Temperature of the scan", "float", "K", 298.15, from_session="temperature_K"),
            Param("alpha", "Temperature coefficient alpha", "float", "1/K", H.ALPHA_IONIC_DEFAULT, required=False,
                  help="0.01 for ionic surfactants; only matters away from 25 C.")],
    methods=[Method("eacn_scan", "Optimal salinity against EACN",
                    "At the optimum HLD = 0, so ln S* = k EACN + alpha dT - Cc: a straight line whose slope is k and "
                    "whose intercept gives Cc.", "Winsor III optimal salinities measured with three or more oils.")],
    run=run_scan, tools=["fit_k_and_cc_from_salinity_scan"], citations=["salager_1979", "schirone_2021"],
    produces=["hld_cc", "hld_k"], unlocks=["hld_value"],
    followups=["Use Cc and k to predict the optimal salinity for another oil.",
               "Blend with a second surfactant of known Cc to move the optimum (Cc mixes by mole fraction)."],
    keywords=["salinity scan", "optimal salinity", "characteristic curvature", "several oils", "phase scan", "measure cc"],
)


# ----------------------------------------------------- HLD of a formulation
def run_hld(inp: RunInput) -> RunResult:
    p, family = inp.params, (inp.method or "ionic")
    preset = p.get("preset") or ""
    cc, k = p.get("cc"), p.get("k")
    calls = []
    if preset:
        if family != "ionic":
            raise ValueError("The preset Cc and k values are for cationic quaternary ammonium surfactants (ionic).")
        pc, _ = H.CATIONIC_QUAT_CC[preset]
        cc = pc if cc in (None, "") else cc
        k = H.CATIONIC_QUAT_K if k in (None, "") else k
    if cc in (None, "") or k in (None, ""):
        raise ValueError("Enter Cc and k (from a salinity scan or the literature), or pick a preset surfactant.")
    cc, k = float(cc), float(k)
    S, eacn, dT = float(p["salinity_pct"]), float(p["eacn"]), _delta_t(p)
    alpha_in = p.get("alpha")
    if family == "ionic":
        alpha = float(alpha_in) if alpha_in not in (None, "") else H.ALPHA_IONIC_DEFAULT
        hld = H.hld_ionic(S, k, eacn, cc, alpha, dT)
        s_opt = H.optimal_salinity_ionic(k, eacn, cc, alpha, dT)
        calls += ["hld.hld_ionic", "hld.optimal_salinity_ionic"]
        form = "HLD = ln S - k EACN - alpha dT + Cc"
    elif family == "nonionic":
        b = p.get("b")
        if b in (None, ""):
            raise ValueError("The nonionic form needs the salinity coefficient b (about 0.13 per g/100 mL for alkyl "
                             "ethoxylates; about 0 for sugar-based surfactants).")
        b = float(b)
        alpha = float(alpha_in) if alpha_in not in (None, "") else H.ALPHA_NONIONIC_DEFAULT
        hld = H.hld_nonionic(S, b, k, eacn, cc, alpha, dT)
        calls.append("hld.hld_nonionic")
        s_opt = (k * eacn + alpha * dT - cc) / b if b > 0 else None      # HLD_nonionic = 0 solved for S
        if s_opt is not None:
            assert abs(H.hld_nonionic(s_opt, b, k, eacn, cc, alpha, dT)) < 1e-9
        form = "HLD = b S - k EACN - alpha dT + Cc"
    else:
        raise ValueError(f"Unknown HLD form {family!r}.")
    if hld < 0:
        state = ("negative: the surfactant favours water (Winsor I, oil-in-water microemulsion or emulsion). More salt, "
                 "a lower-EACN oil" + (" or a higher temperature" if family == "nonionic" else "")
                 + " moves it toward balance.")
    elif hld > 0:
        state = ("positive: the surfactant favours oil (Winsor II, water-in-oil). Less salt or a higher-EACN oil "
                 "moves it toward balance.")
    else:
        state = "zero: the formulation is balanced (Winsor III), where interfacial tension is lowest."
    concl = [f"HLD = {hld:.3g}, {state}"]
    if s_opt is not None and s_opt > 0:
        concl.append(f"The optimal (balanced) salinity for this oil and temperature is {s_opt:.3g} g/100 mL.")
    elif family == "nonionic":
        concl.append("No positive salinity balances this system; change the oil, temperature or surfactant instead.")
    warn = ["HLD values are only as good as Cc, k and the oil's EACN; quote where each came from."]
    if preset:
        warn.append(f"Cc of {preset} and k = {H.CATIONIC_QUAT_K} are the values measured by Schirone et al. (2021) "
                    f"for cationic quaternary ammonium surfactants (k uncertainty +/- {H.CATIONIC_QUAT_K_UNCERTAINTY}).")
    values = [Value("HLD", hld, sig=3), Value("Form used", form), Value("Cc", cc, sig=3), Value("k", k, sig=3),
              Value("Temperature difference from 25 C", dT, "K", 3)]
    if s_opt is not None:
        values.append(Value("Optimal salinity S*", s_opt, "g/100 mL", 3))
    return RunResult(values, [], concl, warn, {"hld": hld}, calls)


HLD_T = Technique(
    id="hld_value", category="Formulation", title="HLD of a surfactant-oil-water formulation", level="measurement",
    summary="Hydrophilic-lipophilic difference of a formulation and its optimal salinity: whether it forms an "
            "oil-in-water, balanced or water-in-oil system.",
    params=[Param("preset", "Surfactant preset (cationic quats)", "choice", "", "", choices=PRESETS, required=False),
            Param("cc", "Characteristic curvature Cc", "float", "", None, required=False, from_session="hld_cc"),
            Param("k", "EACN coefficient k", "float", "", None, required=False, from_session="hld_k",
                  help="About 0.16 for anionic sulfates/sulfonates, 0.7 for quaternary ammonium."),
            Param("b", "Nonionic: salinity coefficient b", "float", "1/(g/100 mL)", None, required=False),
            Param("salinity_pct", "Salinity S (NaCl equivalent)", "float", "g/100 mL", None),
            Param("eacn", "Oil EACN", "float", "", None, help="Carbon number for a linear alkane, e.g. 8 for octane."),
            Param("temperature_K", "Temperature", "float", "K", 298.15, from_session="temperature_K"),
            Param("alpha", "Temperature coefficient alpha (optional)", "float", "1/K", None, required=False,
                  help="Defaults: 0.01 ionic, -0.06 ethoxylated nonionic.")],
    methods=[Method("ionic", "Ionic surfactant",
                    "HLD = ln S - k EACN - alpha dT + Cc: salinity acts through counterion screening (logarithmic).",
                    "Anionic and cationic surfactants."),
             Method("nonionic", "Nonionic (ethoxylated) surfactant",
                    "HLD = b S - k EACN - alpha dT + Cc: salinity dehydrates the EO chains (linear).",
                    "Alcohol ethoxylates and other nonionics; needs b.")],
    run=run_hld, tools=["hld_ionic", "hld_nonionic", "optimal_salinity_ionic"],
    citations=["salager_1979", "schirone_2021"], produces=["hld"],
    followups=["Run a salinity scan with several oils to measure Cc and k for your own surfactant.",
               "HLD replaces HLB when salinity, oil type or temperature matter."],
    keywords=["hld", "hydrophilic lipophilic difference", "microemulsion", "winsor", "oil recovery", "eacn"],
)

TECHNIQUES = [SCAN_T, HLD_T]
