"""Surface tension vs concentration (tensiometry) techniques.

Primary:  CMC from the curve (five estimators the researcher chooses between).
Derived:  maximum surface excess and minimum area per molecule (Gibbs);
          Langmuir vs Frumkin isotherm selection.
"""
from __future__ import annotations

import math

from surfactantkit import adsorption as ads
from surfactantkit import curve_analysis as ca

from .. import plotting as P
from .base import (Column, DatasetSpec, Figure, Method, Param, RunInput, RunResult,
                   Technique, Value)

SYSTEM_TYPES = [
    ("nonionic", "Nonionic surfactant (n = 1)"),
    ("ionic_excess_electrolyte", "Ionic, in excess inert electrolyte (n = 1)"),
    ("ionic_no_added_salt", "Ionic 1:1, no added salt (n = 2)"),
]

TENSIOMETRY = DatasetSpec(
    columns=[
        Column("conc", "Concentration", ["mM", "M", "uM"], ["conc", "c ", "concentration", "mm", "mol"]),
        Column("gamma", "Surface tension", ["mN/m", "dyn/cm"], ["gamma", "tension", "sft", "st ", "mn/m", "dyn"]),
    ],
    min_rows=6,
    example="SDS_surface_tension.csv",
)

TEMPERATURE = Param("temperature_K", "Temperature", "float", "K", 298.15,
                    help="Measurement temperature.", from_session="temperature_K")
SYSTEM = Param("system_type", "Surfactant / electrolyte condition", "choice",
               choices=SYSTEM_TYPES, from_session="system_type",
               help="Sets the Gibbs prefactor n. Not guessed: an ionic surfactant without "
                    "added salt needs n = 2, with excess electrolyte n = 1.")


# ----------------------------------------------------------------- CMC (primary)
CMC_METHODS = [
    Method("rss", "Break-point fit (BIC-selected segments)",
           "Fits straight lines to surface tension vs log10 C before and after the CMC (plus a "
           "low-concentration baseline when the data show one) and places the break where the "
           "total residual is smallest.",
           "Default. Best for a curve with a clear decline and a flat plateau."),
    Method("tangential", "Tangent intersection (Rosen)",
           "Intersection of the steepest pre-CMC line with the post-CMC line, the classical "
           "graphical construction.",
           "When you want the textbook graphical value to compare with published CMCs."),
    Method("derivative", "Steepest-slope point",
           "Midpoint of the adjacent pair with the largest |d gamma / d log10 C|.",
           "Quick estimate; sensitive to noise and point spacing."),
    Method("sigmoid_bootstrap", "Sigmoid fit with 95% confidence interval",
           "Fits a 4-parameter sigmoid to gamma vs log10 C; the CMC is the transition midpoint. "
           "Residual bootstrap (1000 refits) gives a confidence interval.",
           "When you need an uncertainty for the CMC. Note: the midpoint is a different "
           "estimator from a break point and is usually somewhat lower."),
    Method("szyszkowski", "Szyszkowski deviation (cross-check)",
           "Fits the Szyszkowski isotherm to the pre-CMC data and takes the CMC where the "
           "measured points depart from it.",
           "When the plateau has too few points or is not flat (the app flags this)."),
    Method("compare", "Compare all methods",
           "Runs every estimator above on the same curve and plots them together.",
           "Before reporting a CMC, to see how much the value depends on the method."),
]


def _log10(xs):
    return [math.log10(x) for x in xs]


def _break_point_figure(c, g, r, extra_cmc=None, extra_label=None) -> bytes:
    fig, ax = P.new()
    ax.scatter(c, g, s=18, color=P.DATA, zorder=3, label="Measured")
    lx_cmc = math.log10(r.cmc_mM)
    lo, hi = min(c), max(c)
    # pre-CMC line, rebuilt exactly from the toolkit's own fit (slope per log10 C through gamma_cmc),
    # drawn only over the range the toolkit fitted it on
    xs = [r.premicellar_x_min_mM or lo, r.cmc_mM]
    ax.plot(xs, [r.gamma_at_cmc_mN_per_m + r.premicellar_slope_mN_per_m_per_log10C * (math.log10(x) - lx_cmc) for x in xs],
            color=P.FIT, lw=1.6, label="Pre-CMC fit")
    xs = [r.cmc_mM, hi]
    ax.plot(xs, [r.postmicellar_intercept_mN_per_m + r.postmicellar_slope_mN_per_m_per_log10C * math.log10(x) for x in xs],
            color=P.FIT, lw=1.6, ls="--", label="Post-CMC fit")
    if r.n_baseline_points:
        ax.hlines(r.gamma0_mN_m, lo, c[r.n_baseline_points - 1], color=P.MUTED, lw=1.2, label="Baseline")
    ax.axvline(r.cmc_mM, color=P.MARK, lw=1.2, ls=":", label=f"CMC = {r.cmc_mM:.3g} mM")
    if extra_cmc:
        ax.axvline(extra_cmc, color=P.ALT, lw=1.2, ls="-.", label=f"{extra_label} = {extra_cmc:.3g} mM")
    ax.set_xscale("log")
    ax.set_xlabel("Concentration (mM)")
    ax.set_ylabel("Surface tension (mN/m)")
    ax.legend(fontsize=7, loc="best")
    return P.to_png(fig)


def run_cmc_compare(inp: RunInput) -> RunResult:
    """Every estimator on the same curve, side by side: the spread is itself a result."""
    c, g = inp.data["conc"], inp.data["gamma"]
    rows, calls = [], []
    for m in ("rss", "tangential", "derivative"):
        r = ca.cmc_from_surface_tension_curve(c, g, method=m)
        rows.append((next(x.label for x in CMC_METHODS if x.key == m), r.cmc_mM))
        calls.append(f"curve_analysis.cmc_from_surface_tension_curve(method='{m}')")
    base = ca.cmc_from_surface_tension_curve(c, g)
    b = ca.bootstrap_cmc(_log10(c), g, n_boot=1000, ci=0.95, seed=0)
    rows.append(("Sigmoid midpoint", b.cmc_point))
    calls.append("curve_analysis.bootstrap_cmc")
    st = inp.params.get("system_type")
    if st:
        d = ca.cmc_via_szyszkowski_deviation(c, g, base, st, temperature_K=float(inp.params["temperature_K"]))
        calls.append("curve_analysis.cmc_via_szyszkowski_deviation")
        if not d.no_break_found_in_range and d.cmc_mM:
            rows.append(("Szyszkowski deviation", d.cmc_mM))
    vals = [r[1] for r in rows]
    lo, hi = min(vals), max(vals)
    values = [Value(f"CMC, {name}", v, "mM") for name, v in rows]
    values.append(Value("Spread (max / min)", hi / lo, sig=3))
    fig, ax = P.new(16.0, 8.0)
    ax.scatter(c, g, s=18, color=P.DATA, zorder=3, label="Measured")
    colors = [P.FIT, P.ALT, P.MARK, P.MUTED, P.INK]
    for (name, v), col in zip(rows, colors):
        ax.axvline(v, color=col, lw=1.1, ls=":", label=f"{name}: {v:.3g} mM")
    ax.set_xscale("log"); ax.set_xlabel("Concentration (mM)"); ax.set_ylabel("Surface tension (mN/m)")
    ax.legend(fontsize=6, loc="upper left", bbox_to_anchor=(1.02, 1.0))   # outside: never covers the lines
    concl = [f"The estimators place the CMC between {lo:.3g} and {hi:.3g} mM on the same data.",
             "This spread comes from how each method defines the CMC, not from noise. State which method you "
             "report; the break-point fit is the usual choice for a curve with a flat plateau."]
    warnings = []
    if hi / lo > 1.5:
        warnings.append("The methods disagree by more than 50%: the curve has too few points near the CMC "
                        "or no clear plateau. More concentrations around the transition would settle it.")
    if ca.plateau_is_statistically_suspect(base):
        warnings.append("The break-point plateau is statistically suspect (too few or non-flat points).")
    return RunResult(values, [Figure("cmc_compare", P.to_png(fig), "CMC from every estimator on the same curve.")],
                     concl, warnings, {}, calls)


def run_cmc(inp: RunInput) -> RunResult:
    if inp.method == "compare":
        return run_cmc_compare(inp)
    c, g = inp.data["conc"], inp.data["gamma"]
    calls, warnings, extra = [], [], {}
    method = inp.method or "rss"
    base_method = method if method in ("rss", "tangential", "derivative") else "rss"
    r = ca.cmc_from_surface_tension_curve(c, g, method=base_method)
    calls.append(f"curve_analysis.cmc_from_surface_tension_curve(method='{base_method}')")
    suspect = ca.plateau_is_statistically_suspect(r)
    calls.append("curve_analysis.plateau_is_statistically_suspect")

    cmc = r.cmc_mM
    values = []
    figure_extra = None
    if method == "sigmoid_bootstrap":
        b = ca.bootstrap_cmc(_log10(c), g, n_boot=1000, ci=0.95, seed=0)
        calls.append("curve_analysis.bootstrap_cmc(n_boot=1000, ci=0.95)")
        cmc = b.cmc_point
        values += [Value("CMC (sigmoid midpoint)", b.cmc_point, "mM"),
                   Value("95% CI, lower", b.cmc_ci_low, "mM"),
                   Value("95% CI, upper", b.cmc_ci_high, "mM"),
                   Value("Bootstrap converged", b.converged)]
        if not b.converged:
            warnings.append(f"Bootstrap did not converge ({b.n_failed} of {b.n_boot_requested} refits failed); "
                            "treat the interval as unreliable.")
        if b.caveat:
            warnings.append(b.caveat)
        extra = {"cmc_ci_low_mM": b.cmc_ci_low, "cmc_ci_high_mM": b.cmc_ci_high}
        figure_extra = (b.cmc_point, "Sigmoid midpoint")
    elif method == "szyszkowski":
        st = inp.params.get("system_type")
        if not st:
            raise ValueError("The Szyszkowski cross-check needs the surfactant / electrolyte condition.")
        d = ca.cmc_via_szyszkowski_deviation(c, g, r, st, temperature_K=float(inp.params["temperature_K"]))
        calls.append("curve_analysis.cmc_via_szyszkowski_deviation")
        if d.no_break_found_in_range or d.cmc_mM is None:
            warnings.append(f"No departure from the Szyszkowski isotherm found in range: {d.reason}")
        else:
            cmc = d.cmc_mM
            values += [Value("CMC (Szyszkowski deviation)", d.cmc_mM, "mM"),
                       Value("Isotherm fit R^2", d.fit_r_squared, sig=4)]
            figure_extra = (d.cmc_mM, "Szyszkowski deviation")

    values += [
        Value("CMC (break point)" if method != "rss" else "CMC", r.cmc_mM, "mM"),
        Value("Surface tension at CMC", r.gamma_at_cmc_mN_per_m, "mN/m"),
        Value("Baseline surface tension (gamma0)", r.gamma0_mN_m, "mN/m"),
        Value("Pre-CMC slope", r.premicellar_slope_mN_per_m_per_log10C, "mN/m per decade"),
        Value("Pre-CMC fit R^2", r.r_squared_premicellar),
        Value("Points before / after CMC", f"{r.n_premicellar_points} / {r.n_postmicellar_points}"),
        Value("C20", r.c20_mM, "mM"),
        Value("pC20", r.pC20, sig=3),
    ]
    if r.c20_mM:
        values.append(Value("CMC / C20", r.cmc_mM / r.c20_mM, sig=3))

    if r.n_premicellar_points < 3:
        warnings.append(f"The pre-CMC decline is defined by only {r.n_premicellar_points} points, so its R^2 = 1 is "
                        "trivial and the slope (used for Gamma_max and A_min) is not statistically constrained. "
                        "Measure more concentrations between the baseline and the CMC.")
    if suspect and method in ("rss", "tangential", "derivative"):
        warnings.append("The post-CMC plateau has too few points or is not flat enough to trust this break "
                        "point. Run the Szyszkowski deviation method as a cross-check before reporting the CMC.")

    pi_cmc = r.gamma0_mN_m - r.gamma_at_cmc_mN_per_m
    conclusion = [
        f"Micelles start forming at about {cmc:.3g} mM: above this concentration added surfactant goes into "
        f"micelles instead of the surface, so surface tension stops falling.",
        f"The surfactant lowers surface tension to {r.gamma_at_cmc_mN_per_m:.3g} mN/m at the CMC "
        f"(effectiveness; a reduction of {pi_cmc:.3g} mN/m from the baseline).",
    ]
    if r.pC20:
        conclusion.append(f"pC20 = {r.pC20:.3g} (efficiency): the higher pC20, the less surfactant is needed to "
                          f"cut surface tension by 20 mN/m.")
    if suspect and method in ("rss", "tangential", "derivative"):
        conclusion.append("Treat this CMC as provisional until the cross-check agrees (see warning).")

    fig = Figure("cmc_tensiometry", _break_point_figure(c, g, r, *(figure_extra or (None, None))),
                 "Surface tension against concentration with the fitted segments and the CMC.")
    provides = {
        "cmc_mM": cmc, "cmc_source": "tensiometry", "gamma_cmc_mN_m": r.gamma_at_cmc_mN_per_m,
        "gamma0_mN_m": r.gamma0_mN_m, "premicellar_slope_ln": r.premicellar_slope_mN_per_m_per_lnC,
        "n_premicellar_points": r.n_premicellar_points,
        "tensiometry_pre_c": [x for x in c if x < r.cmc_mM],
        "tensiometry_pre_g": [y for x, y in zip(c, g) if x < r.cmc_mM],
        **extra,
    }
    return RunResult(values, [fig], conclusion, warnings, provides, calls)


CMC_TENSIOMETRY = Technique(
    id="cmc_tensiometry", category="Micellization", title="CMC from surface tension",
    level="primary",
    summary="Critical micelle concentration, surface tension at the CMC, efficiency (pC20) "
            "from a surface tension vs concentration curve.",
    dataset=TENSIOMETRY, params=[TEMPERATURE, Param(**{**SYSTEM.__dict__, "required": False})],
    methods=CMC_METHODS, run=run_cmc,
    tools=["cmc_from_surface_tension_curve", "bootstrap_cmc", "cmc_via_szyszkowski_deviation"],
    citations=["rosen_kunjappu_2012", "szyszkowski_1908"],
    produces=["cmc_mM", "premicellar_slope_ln", "gamma0_mN_m", "tensiometry_pre_c", "tensiometry_pre_g"],
    unlocks=["surface_excess", "isotherm_selection", "gibbs_energy_micellization", "wetting_solution"],
    followups=[
        "Compute the maximum surface excess and area per molecule from the pre-CMC slope (Gibbs).",
        "Check whether adsorption is ideal (Langmuir) or shows lateral interaction (Frumkin).",
        "Combine the CMC with counterion binding from conductivity to get the free energy of micellization.",
        "Repeat at 3 or more temperatures to get enthalpy and entropy of micellization (van't Hoff).",
    ],
    keywords=["cmc", "critical micelle", "surface tension", "tensiometry", "sft", "gamma", "pc20", "c20"],
)


# ------------------------------------------------------ surface excess (derived)
def run_surface_excess(inp: RunInput) -> RunResult:
    st, T = inp.params["system_type"], float(inp.params["temperature_K"])
    slope = inp.session["premicellar_slope_ln"]
    gmax = ads.gibbs_gamma_max(slope, st, T)
    amin_nm2 = ads.gibbs_a_min(gmax)
    n = 2 if st == "ionic_no_added_salt" else 1
    values = [Value("Maximum surface excess, Gamma_max", gmax * 1e6, "umol/m^2"),
              Value("Minimum area per molecule, A_min", amin_nm2, "nm^2"),
              Value("A_min", amin_nm2 * 100, "A^2"),
              Value("Gibbs prefactor n", n)]
    conclusion = [
        f"At saturation the interface holds about {gmax * 1e6:.3g} umol of surfactant per m^2, "
        f"i.e. each molecule occupies about {amin_nm2 * 100:.3g} A^2.",
        "A small area per molecule means tight packing at the interface; a large one points to a bulky or "
        "charged head group, or to an interface that is not fully saturated.",
    ]
    warnings = []
    if inp.session.get("n_premicellar_points", 3) < 3:
        warnings.append("Gamma_max comes from a pre-CMC slope through only "
                        f"{inp.session['n_premicellar_points']} points; treat it as an estimate.")
    if amin_nm2 * 100 > 150:
        warnings.append("A_min above 150 A^2 is unusually large; check the condition (n) and whether the "
                        "pre-CMC region was fitted correctly.")
    return RunResult(values, [], conclusion, warnings,
                     {"gamma_max_mol_m2": gmax, "a_min_nm2": amin_nm2, "system_type": st, "temperature_K": T},
                     ["adsorption.gibbs_gamma_max", "adsorption.gibbs_a_min"])


SURFACE_EXCESS = Technique(
    id="surface_excess", category="Adsorption", title="Surface excess and area per molecule",
    level="derived",
    summary="Gibbs maximum surface excess and minimum area per molecule from the pre-CMC slope.",
    params=[TEMPERATURE, SYSTEM],
    methods=[Method("gibbs", "Gibbs adsorption equation",
                    "Gamma_max = -(1 / nRT) d gamma / d ln C, using the slope just below the CMC.",
                    "Standard route whenever the pre-CMC region is linear in log C.")],
    requires=["premicellar_slope_ln"], run=run_surface_excess,
    tools=["gibbs_gamma_max", "gibbs_a_min"], citations=["rosen_kunjappu_2012"],
    produces=["gamma_max_mol_m2", "a_min_nm2"],
    unlocks=["isotherm_selection", "packing_parameter"],
    followups=["Test Langmuir vs Frumkin adsorption with these values held fixed.",
               "Estimate the packing parameter and expected micelle shape from A_min and the tail length."],
    keywords=["surface excess", "gamma max", "area per molecule", "amin", "gibbs", "packing"],
)


# --------------------------------------------------- isotherm selection (derived)
def run_isotherm(inp: RunInput) -> RunResult:
    s = inp.session
    st, T = inp.params["system_type"], float(inp.params["temperature_K"])
    c, g = s["tensiometry_pre_c"], s["tensiometry_pre_g"]
    if len(c) < 4:
        raise ValueError(f"Only {len(c)} points lie below the CMC; at least 4 are needed to compare isotherms.")
    r = ads.select_isotherm_model(c, g, s["gamma0_mN_m"], s["gamma_max_mol_m2"], st, T)
    values = [Value("Selected model", r.selected_model),
              Value("Langmuir K", r.langmuir_K, "1/mM"), Value("Langmuir R^2", r.langmuir_r_squared),
              Value("Frumkin K", r.frumkin_K, "1/mM"), Value("Frumkin a", r.frumkin_a, sig=3),
              Value("Frumkin R^2", r.frumkin_r_squared),
              Value("Delta BIC (Langmuir - Frumkin)", r.delta_bic, sig=3)]
    if r.selected_model.lower().startswith("frumkin"):
        sign = "attractive" if (r.frumkin_a or 0) > 0 else "repulsive"
        concl = [f"The data justify the Frumkin model: adsorbed molecules show {sign} lateral interaction "
                 f"(a = {r.frumkin_a:.3g}), beyond what ideal Langmuir adsorption explains."]
    else:
        concl = ["Ideal Langmuir (Szyszkowski) adsorption describes the data; the extra Frumkin interaction "
                 "parameter does not earn its place by BIC."]
    concl.append("A BIC difference below about 2 means the two models are practically indistinguishable.")
    fig, ax = P.new()
    ax.scatter(c, g, s=18, color=P.DATA, zorder=3, label="Measured (pre-CMC)")
    ax.set_xscale("log"); ax.set_xlabel("Concentration (mM)"); ax.set_ylabel("Surface tension (mN/m)")
    ax.legend(fontsize=7, loc="best")
    return RunResult(values, [Figure("isotherm", P.to_png(fig), "Pre-CMC data used for the isotherm comparison.")],
                     concl, list(r.warnings), {"isotherm_model": r.selected_model},
                     ["adsorption.select_isotherm_model"])


ISOTHERM = Technique(
    id="isotherm_selection", category="Adsorption", title="Langmuir vs Frumkin adsorption",
    level="derived",
    summary="Decides by BIC whether adsorption is ideal (Langmuir) or shows lateral interaction (Frumkin).",
    params=[TEMPERATURE, SYSTEM],
    methods=[Method("bic", "BIC model selection",
                    "Both isotherms are fitted with the same gamma0 and Gamma_max; Frumkin's extra parameter "
                    "is kept only if it lowers BIC.", "Whenever there are 4 or more pre-CMC points.")],
    requires=["tensiometry_pre_c", "gamma0_mN_m", "gamma_max_mol_m2"], run=run_isotherm,
    tools=["select_isotherm_model", "frumkin_fit_K_and_a", "szyszkowski_fit_K"],
    citations=["frumkin_1925", "szyszkowski_1908"],
    followups=["Report the selected isotherm with its K (and a) in your adsorption discussion."],
    keywords=["isotherm", "langmuir", "frumkin", "szyszkowski", "lateral interaction"],
)

TECHNIQUES = [CMC_TENSIOMETRY, SURFACE_EXCESS, ISOTHERM]
