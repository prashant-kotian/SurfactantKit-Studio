"""Binary surfactant mixtures: CMC of the mixture vs composition.

Primary: model selection between ideal mixing (Clint), regular-solution
interaction (Rubingh, one beta) and the asymmetric Margules model (EOMMM, two
parameters), by BIC on the measured cmc_mix(alpha1) series; Rubingh beta,
micellar composition, activity coefficients and excess free energy per point.
"""
from __future__ import annotations

import math

from surfactantkit import mixed_micelle as mm
from surfactantkit.mixture_model_selection import select_mixture_model

from .. import plotting as P
from .base import Column, DatasetSpec, Figure, Method, Param, RunInput, RunResult, Technique, Value

MIXTURE = DatasetSpec(
    columns=[
        Column("alpha1", "Mole fraction of surfactant 1 in the total surfactant (alpha1)", ["fraction"],
               ["alpha", "mole fraction", "x1", "fraction"]),
        Column("cmc_mix", "CMC of the mixture", ["mM", "M", "uM"], ["cmc"]),
    ],
    min_rows=3,
    example="synthetic_mixed_cmc.csv",
)

NAMES = {"clint_ideal": "Clint (ideal mixing)", "rubingh_regular_solution": "Rubingh (regular solution, one beta)",
         "eommm_asymmetric_margules": "EOMMM (asymmetric Margules, two parameters)"}


def run_mixture(inp: RunInput) -> RunResult:
    a, c = inp.data["alpha1"], inp.data["cmc_mix"]
    if any(not 0 < x < 1 for x in a):
        raise ValueError("alpha1 must lie strictly between 0 and 1 (pure components go in the CMC1/CMC2 fields).")
    cmc1, cmc2 = float(inp.params["cmc1_mM"]), float(inp.params["cmc2_mM"])
    T = float(inp.params["temperature_K"])
    sel = select_mixture_model(a, c, cmc1, cmc2)
    reg = mm.rubingh_beta_regression(a, c, cmc1, cmc2)
    calls = ["mixture_model_selection.select_mixture_model", "mixed_micelle.rubingh_beta_regression"]
    cand = {k.name: k for k in sel.candidates}
    values = [Value("Selected model (BIC)", NAMES.get(sel.selected_model, sel.selected_model))]
    for name, k in cand.items():
        values.append(Value(f"BIC, {NAMES.get(name, name)}", k.bic, sig=4))
    beta = reg.beta_mean
    values += [Value("Rubingh beta (mean over compositions)", beta, sig=3),
               Value("Rubingh beta, standard deviation", reg.beta_std, sig=2),
               Value("Compositions used / skipped", f"{reg.n_points_used} / {reg.n_points_skipped}")]
    if "eommm_asymmetric_margules" in cand:
        p = cand["eommm_asymmetric_margules"].params
        values += [Value("EOMMM W12", p.get("W12"), sig=3), Value("EOMMM W21", p.get("W21"), sig=3)]

    # per-composition micellar composition, activity coefficients, excess free energy (Rubingh)
    rows = []
    for a1, cm, x1 in zip(reg.alpha1_used, [c[a.index(v)] for v in reg.alpha1_used], reg.x1_values):
        f1, f2 = mm.activity_coefficients(x1, beta)
        g = mm.excess_free_energy(x1, f1, f2, T)
        rows.append((a1, x1, f1, f2, g))
    calls += ["mixed_micelle.activity_coefficients", "mixed_micelle.excess_free_energy"]
    for a1, x1, f1, f2, g in rows:
        values.append(Value(f"alpha1 = {a1:g}: micellar x1 / f1 / f2 / G_ex",
                            f"{x1:.3f} / {f1:.3f} / {f2:.3f} / {g:.2f} kJ/mol"))

    ln_ratio = abs(math.log(cmc1 / cmc2))
    concl = []
    if sel.selected_model == "clint_ideal":
        concl.append("The data are consistent with ideal mixing: the two surfactants form micelles together "
                     "without measurable extra interaction.")
    else:
        concl.append(f"Mixing is non-ideal (best model: {NAMES.get(sel.selected_model)}). Rubingh beta = {beta:.2f}: "
                     + ("negative, so the two surfactants attract each other in the micelle."
                        if beta < 0 else "positive, so they repel each other in the micelle."))
    if beta < 0 and abs(beta) > ln_ratio:
        concl.append(f"Synergism in mixed micelle formation is expected: beta is negative and |beta| ({abs(beta):.2f}) "
                     f"exceeds |ln(CMC1/CMC2)| ({ln_ratio:.2f}), so some mixtures should have a CMC below both "
                     "pure components (Rosen's criterion).")
    elif beta < 0:
        concl.append(f"beta is negative but |beta| ({abs(beta):.2f}) does not exceed |ln(CMC1/CMC2)| ({ln_ratio:.2f}): "
                     "attraction, but no mixture CMC below both pure-component CMCs is expected.")
    warnings = []
    if reg.beta_std and abs(beta) > 0 and reg.beta_std / abs(beta) > 0.3:
        warnings.append("beta varies strongly with composition (std > 30% of the mean); a single regular-solution "
                        "beta may not describe this system, check whether EOMMM fits better.")
    if reg.n_points_skipped:
        warnings.append(f"{reg.n_points_skipped} composition(s) had no valid Rubingh solution and were skipped.")
    if len(a) < 5:
        warnings.append("Fewer than 5 compositions: the model comparison has little power.")

    fig, ax = P.new()
    order = sorted(range(len(a)), key=lambda i: a[i])
    ax.scatter([a[i] for i in order], [c[i] for i in order], s=22, color=P.DATA, zorder=3, label="Measured")
    grid = [i / 100 for i in range(1, 100)]
    ax.plot(grid, [mm.clint_ideal_cmc(x, cmc1, cmc2) for x in grid], color=P.MUTED, ls="--", lw=1.3,
            label="Clint (ideal)")
    for name, col in (("rubingh_regular_solution", P.FIT), ("eommm_asymmetric_margules", P.ALT)):
        if name in cand:
            pred = cand[name].predicted_cmc_mix
            ax.plot([a[i] for i in order], [pred[i] for i in order], color=col, lw=1.4, marker="o", ms=3,
                    label=NAMES[name])
    ax.set_xlabel("alpha1 (mole fraction of surfactant 1)")
    ax.set_ylabel("CMC of mixture (mM)")
    ax.legend(fontsize=6, loc="best")
    return RunResult(values, [Figure("mixture", P.to_png(fig), "Mixture CMC against composition with the fitted models.")],
                     concl, warnings + [f"Not compared: {e}" for e in sel.excluded_models],
                     {"rubingh_beta": beta, "mixture_model": sel.selected_model}, calls)


MIXED_MICELLES = Technique(
    id="mixed_micelles", category="Mixtures", title="Mixed micelles: ideal or interacting?",
    level="primary",
    summary="From the CMC of binary mixtures at several compositions: whether mixing is ideal (Clint) or "
            "interacting (Rubingh beta, EOMMM), micellar composition, activity coefficients, synergism.",
    dataset=MIXTURE,
    params=[Param("cmc1_mM", "CMC of pure surfactant 1", "float", "mM", None),
            Param("cmc2_mM", "CMC of pure surfactant 2", "float", "mM", None),
            Param("temperature_K", "Temperature", "float", "K", 298.15, from_session="temperature_K")],
    methods=[Method("bic", "Model selection (Clint vs Rubingh vs EOMMM)",
                    "Fits all three mixing models to the measured series and keeps the one with the lowest BIC, "
                    "so an extra interaction parameter is used only when the data justify it.",
                    "Default; needs 3 or more mixture compositions, 5 or more recommended.")],
    run=run_mixture, tools=["select_mixture_model", "rubingh_beta_regression", "clint_ideal_cmc",
                            "activity_coefficients", "excess_free_energy"],
    citations=["clint_1975", "rubingh_1979", "rosen_kunjappu_2012"],
    produces=["rubingh_beta"],
    followups=["Report beta with the compositions used; a negative beta means attraction between the surfactants.",
               "If synergism is expected, measure more compositions around the predicted CMC minimum.",
               "Measure surface tension of the mixtures to test synergism in surface tension reduction as well."],
    keywords=["mixture", "mixed micelle", "binary", "rubingh", "clint", "synergism", "synergy", "interaction parameter",
              "beta parameter", "mole fraction", "two surfactants", "blend"],
)

TECHNIQUES = [MIXED_MICELLES]
