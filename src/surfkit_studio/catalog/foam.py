"""Foam: how much forms and how long it lasts.

Primary: foam height against time (Ross-Miles pour test or any decay curve),
with exponential vs logarithmic decay chosen by BIC. Measurement: Bikerman's
foaminess index from a steady sparging test. Derived: Gibbs-Marangoni surface
elasticity from the fitted adsorption isotherm, a stability proxy (it says
nothing about how much foam forms).
"""
from __future__ import annotations

import math
import re

from surfactantkit import foam as F

from .. import plotting as P
from .base import Column, DatasetSpec, Figure, Method, Param, RunInput, RunResult, Technique, Value
from .tensiometry import SYSTEM, TEMPERATURE

DECAY = DatasetSpec(
    columns=[Column("t", "Time after foam formation", ["min", "s", "h"], ["time", "min", "t "],
                    factors={"min": 1.0, "s": 1 / 60, "h": 60.0}),
             Column("h", "Foam height", ["mm", "cm"], ["height", "foam", "h "], factors={"mm": 1.0, "cm": 10.0})],
    min_rows=3, example="synthetic_foam_decay.csv")


# ----------------------------------------------------------- decay (primary)
def run_decay(inp: RunInput) -> RunResult:
    t, h = inp.data["t"], inp.data["h"]
    r = F.select_foam_decay_model(t, h)
    calls = ["foam.select_foam_decay_model"]
    values, warn = [], []
    if 0.0 in t:
        rm = F.ross_miles_summary(t, h)
        calls.insert(0, "foam.ross_miles_summary")
        values.append(Value("Initial foam height (t = 0)", rm.initial_height_mm, "mm", 3))
        for tm in (1.0, 3.0, 5.0):
            if tm in rm.heights_by_time_mm:
                values.append(Value(f"Height at {tm:g} min (fraction retained)",
                                    f"{rm.heights_by_time_mm[tm]:.3g} mm ({100 * rm.fraction_retained_at[tm]:.0f}%)"))
    else:
        warn.append("No reading at t = 0, so the Ross-Miles initial height and retained fractions are not reported.")
    best = "exponential" if r.selected_model == "exponential" else "logarithmic"
    values += [Value("Better decay model (BIC)", best),
               Value("Exponential half-life", r.exponential_half_life_min, "min", 3),
               Value("Exponential R^2", r.exponential_r_squared, sig=3),
               Value("Logarithmic slope (mm per ln min)", r.logarithmic_slope, sig=3),
               Value("Logarithmic R^2", r.logarithmic_r_squared, sig=3),
               Value("Delta BIC (exponential - logarithmic)", r.delta_bic, sig=3)]
    fig, ax = P.new()
    ax.scatter(t, h, s=20, color=P.DATA, zorder=3, label="Measured")
    xs = [max(t) * i / 100 for i in range(101)]
    # OLS intercept of ln h = ln a - k t over the points with h > 0 (the toolkit fits the same line)
    a_exp = math.exp(sum(math.log(y) + r.exponential_rate_constant_per_min * x for x, y in zip(t, h) if y > 0) /
                     max(1, sum(1 for y in h if y > 0)))
    ax.plot(xs, [a_exp * math.exp(-r.exponential_rate_constant_per_min * x) for x in xs], color=P.FIT, lw=1.5,
            label="Exponential")
    xl = [x for x in xs if x > 0]
    ax.plot(xl, [r.logarithmic_intercept_mm - r.logarithmic_slope * math.log(x) for x in xl], color=P.ALT, lw=1.2,
            ls="--", label="Logarithmic")
    ax.set_xlabel("Time (min)"); ax.set_ylabel("Foam height (mm)"); ax.set_ylim(bottom=0)
    ax.legend(fontsize=7, loc="best")
    concl = [(f"Foam decays roughly first-order with a half-life of {r.exponential_half_life_min:.3g} min."
              if best == "exponential" else
              "Foam height falls with the logarithm of time: a fast initial collapse followed by a long-lived "
              "residual foam, which a single half-life would misdescribe."),
             "A BIC difference below about 2 means the two decay forms are practically indistinguishable."]
    return RunResult(values, [Figure("foam_decay", P.to_png(fig), "Foam height against time with both decay models.")],
                     concl, warn, {"foam_half_life_min": r.exponential_half_life_min}, calls)


DECAY_T = Technique(
    id="foam_decay", category="Foam", title="Foam stability from foam height decay", level="primary",
    summary="Ross-Miles readings (initial height, retention at 1, 3 and 5 min) and the foam decay law "
            "(exponential half-life or logarithmic) chosen by BIC.",
    dataset=DECAY,
    methods=[Method("bic", "Exponential vs logarithmic decay (BIC)",
                    "h = h0 exp(-k t) (half-life ln 2 / k) against h = a - b ln t; both have two parameters, so the "
                    "lower residual wins.", "Any foam height-time series with 3 or more points; include t = 0 for "
                    "a Ross-Miles summary.")],
    run=run_decay, tools=["ross_miles_summary", "select_foam_decay_model"],
    citations=["ross_miles_1941"], produces=["foam_half_life_min"],
    followups=["Compare half-lives across surfactants at the same concentration and temperature.",
               "Relate stability to the surface elasticity from the adsorption isotherm."],
    keywords=["foam", "ross-miles", "ross miles", "foam height", "foam stability", "foam decay", "half-life"],
)


# -------------------------------------------------------- Bikerman (measurement)
def run_bikerman(inp: RunInput) -> RunResult:
    p = inp.params
    v, q = float(p["foam_volume_mL"]), float(p["gas_flow_mL_s"])
    sigma = F.bikerman_foaminess_index(v, q)
    concl = [f"Foaminess index Sigma = {sigma:.3g} s: on average a gas bubble spends about {sigma:.3g} s in the "
             "foam before it bursts.",
             "Sigma is only comparable between tests run in the same column at gas flows in the steady regime; "
             "repeat at two or three flow rates to confirm the foam volume grows in proportion to the flow."]
    return RunResult([Value("Bikerman foaminess index Sigma", sigma, "s", 3)], [], concl, [],
                     {"bikerman_sigma_s": sigma}, ["foam.bikerman_foaminess_index"])


BIKERMAN = Technique(
    id="foam_bikerman", category="Foam", title="Foaminess (Bikerman index)", level="measurement",
    summary="Bikerman's foaminess index from a steady sparging test: steady foam volume divided by gas flow rate.",
    params=[Param("foam_volume_mL", "Steady-state foam volume", "float", "mL", None),
            Param("gas_flow_mL_s", "Gas flow rate", "float", "mL/s", None,
                  help="Use foam height (cm) and superficial gas velocity (cm/s) instead if you prefer; the ratio "
                       "is the same.")],
    methods=[Method("bikerman", "Bikerman index", "Sigma = V_foam / Q_gas, the mean bubble lifetime in the "
                    "steady foam.", "Continuous sparging through a porous frit at constant gas flow.")],
    run=run_bikerman, tools=["bikerman_foaminess_index"], citations=["bikerman_1938"],
    followups=["Pair foaminess (how much forms) with a decay curve (how long it lasts)."],
    keywords=["bikerman", "foaminess", "sparging", "foam volume", "foamability", "foaming ability"],
)


# ------------------------------------------------------ elasticity (derived)
def _concs(text) -> list[float]:
    vals = [float(x) for x in re.split(r"[,;\s]+", str(text or "").strip()) if x]
    if not vals or any(v <= 0 for v in vals):
        raise ValueError("Enter one or more positive concentrations in mM, e.g. 0.5, 1, 2, 4.")
    return sorted(vals)


def run_elasticity(inp: RunInput) -> RunResult:
    s, p = inp.session, inp.params
    K = s.get("isotherm_K_per_mM")
    if not K:
        raise ValueError("The isotherm analysis did not return an adsorption constant K.")
    a, gm = float(s.get("isotherm_a") or 0.0), float(s["gamma_max_mol_m2"])
    st, T = p["system_type"], float(p.get("temperature_K") or 298.15)
    cs = _concs(p.get("concentrations_mM"))
    cmc = s.get("cmc_mM")
    rows, warn = [], []
    for c in cs:
        r = F.foam_stability_elasticity_summary(c, gm, float(K), st, a, T)
        rows.append((c, r))
        if r.high_theta_warning and r.high_theta_warning not in warn:
            warn.append(r.high_theta_warning)
    if cmc and max(cs) > float(cmc):
        warn.append(f"Concentrations above the CMC ({float(cmc):.3g} mM) are outside the isotherm's range: above "
                    "the CMC the monomer concentration stays near the CMC.")
    values = [Value(f"E0 at {c:g} mM (coverage {100 * r.theta:.0f}%)", r.gibbs_marangoni_elasticity_mN_per_m, "mN/m", 3)
              for c, r in rows]
    values.append(Value("Isotherm used", f"{rows[0][1].isotherm_model_used} (K = {float(K):.3g} 1/mM"
                                         + (f", a = {a:.3g})" if a else ")")))
    figs = []
    if len(rows) > 1:
        fig, ax = P.new()
        ax.plot([c for c, _ in rows], [r.gibbs_marangoni_elasticity_mN_per_m for _, r in rows], "o-",
                color=P.DATA, ms=4)
        ax.set_xscale("log"); ax.set_xlabel("Concentration (mM)"); ax.set_ylabel("Gibbs elasticity E0 (mN/m)")
        figs.append(Figure("elasticity", P.to_png(fig), "Gibbs-Marangoni elasticity against concentration."))
    best = max(rows, key=lambda x: x[1].gibbs_marangoni_elasticity_mN_per_m)
    concl = [rows[0][1].interpretation,
             f"Among the concentrations entered, the film is most elastic at {best[0]:g} mM "
             f"(E0 = {best[1].gibbs_marangoni_elasticity_mN_per_m:.3g} mN/m)."]
    return RunResult(values, figs, concl, warn, {"gibbs_elasticity_mN_m": best[1].gibbs_marangoni_elasticity_mN_per_m},
                     ["foam.foam_stability_elasticity_summary"])


ELASTICITY = Technique(
    id="foam_elasticity", category="Foam", title="Foam film elasticity (Gibbs-Marangoni)", level="derived",
    summary="Surface dilational (Gibbs-Marangoni) elasticity of the adsorbed layer from the fitted isotherm: a "
            "proxy for how well foam films heal thin spots.",
    params=[Param("concentrations_mM", "Concentrations to evaluate", "text", "mM", "",
                  help="One or more values below the CMC, e.g. 0.5, 1, 2, 4."),
            SYSTEM, TEMPERATURE],
    methods=[Method("gibbs_marangoni", "Gibbs-Marangoni elasticity",
                    "E0 = -Gamma (d gamma / d Gamma) from the Langmuir or Frumkin isotherm fitted to your tension "
                    "data; higher E0 resists film thinning.",
                    "After the isotherm analysis; compare concentrations or surfactants, not absolute lifetimes.")],
    requires=["isotherm_K_per_mM", "gamma_max_mol_m2"], run=run_elasticity,
    tools=["foam_stability_elasticity_summary"], citations=["georgieva_2009"],
    followups=["Check the elasticity ranking against a measured foam decay half-life."],
    keywords=["elasticity", "marangoni", "gibbs elasticity", "film elasticity", "dilational"],
)

TECHNIQUES = [DECAY_T, BIKERMAN, ELASTICITY]
