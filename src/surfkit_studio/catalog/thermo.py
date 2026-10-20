"""Conductivity and micellization thermodynamics.

Primary:  CMC and counterion binding from a conductivity curve;
          van't Hoff analysis from CMC measured at several temperatures.
Derived:  standard free energy of micellization from a CMC.

Convention used throughout, stated to the researcher: for an ionic
surfactant deltaG_mic = (1 + beta) RT ln X_cmc, beta = degree of counterion
binding (= 1 - alpha, alpha = degree of ionization). SurfactantKit's
functions take the factor explicitly, so the app passes (1 + beta) itself.
"""
from __future__ import annotations

from surfactantkit import curve_analysis as ca
from surfactantkit import thermodynamics as th

from .. import plotting as P
from .base import (Column, DatasetSpec, Figure, Method, Param, RunInput, RunResult,
                   Technique, Value)

CONDUCTIVITY = DatasetSpec(
    columns=[
        Column("conc", "Concentration", ["mM", "M", "uM"], ["conc", "concentration", "mm", "mol"]),
        Column("kappa", "Specific conductivity", ["uS/cm", "mS/cm", "S/m"], ["kappa", "cond", "us/cm", "ms/cm", "k "]),
    ],
    min_rows=6,
    example="synthetic_conductivity.csv",
)

VANT_HOFF = DatasetSpec(
    columns=[
        Column("T", "Temperature", ["K", "C"], ["temp", "t ", "k)", "(c)", "deg"]),
        Column("cmc", "CMC", ["mM", "M", "uM"], ["cmc"]),
    ],
    min_rows=3,
    example="synthetic_cmc_vs_T.csv",
)

BETA = Param("beta", "Counterion binding, beta", "float", "", None, required=False,
             from_session="beta",
             help="Fraction of counterion charge bound to the micelle (0 to 1). Comes from the conductivity "
                  "technique, or enter a literature value. Leave empty for a nonionic surfactant.")
TEMPERATURE = Param("temperature_K", "Temperature", "float", "K", 298.15, from_session="temperature_K")


# --------------------------------------------------------- conductivity (primary)
def run_conductivity(inp: RunInput) -> RunResult:
    c, k = inp.data["conc"], inp.data["kappa"]
    r = ca.cmc_from_conductivity_curve(c, k, method=inp.method or "rss")
    beta = r.counterion_binding_degree
    alpha = 1 - beta if beta is not None else None
    values = [Value("CMC", r.cmc_mM, "mM"),
              Value("Slope below CMC (S1)", r.slope_below_cmc, "conductivity unit per mM"),
              Value("Slope above CMC (S2)", r.slope_above_cmc, "conductivity unit per mM"),
              Value("Degree of ionization, alpha = S2/S1", alpha, sig=3),
              Value("Counterion binding, beta = 1 - alpha", beta, sig=3),
              Value("R^2 below / above", f"{r.r_squared_below_cmc:.4f} / {r.r_squared_above_cmc:.4f}"),
              Value("Points below / above", f"{r.n_points_below_cmc} / {r.n_points_above_cmc}")]
    conclusion = [
        f"The conductivity slope changes at {r.cmc_mM:.3g} mM, where micelles begin to form.",
        f"Above the CMC conductivity rises more slowly because micelles bind part of their counterions: "
        f"about {beta * 100:.0f}% of the charge is neutralised by bound counterions (beta = {beta:.2f}).",
        "beta is needed for the free energy of micellization of an ionic surfactant.",
    ]
    warnings = []
    if not 0 < beta < 1:
        warnings.append("beta outside 0 to 1: the two segments are not a normal conductivity break; check the data.")
    if min(r.n_points_below_cmc, r.n_points_above_cmc) < 4:
        warnings.append("Fewer than 4 points on one side of the CMC; the slopes, and so beta, are poorly determined.")
    fig, ax = P.new()
    ax.scatter(c, k, s=18, color=P.DATA, zorder=3, label="Measured")
    # the toolkit returns slopes only; draw each segment's least-squares line over the same point split
    nb = r.n_points_below_cmc
    for xs, ys, ls, lab in ((c[:nb], k[:nb], "-", "Fit below CMC"), (c[nb:], k[nb:], "--", "Fit above CMC")):
        if len(xs) >= 2:
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
            ax.plot([xs[0], xs[-1]], [my + b * (xs[0] - mx), my + b * (xs[-1] - mx)],
                    color=P.FIT, lw=1.4, ls=ls, label=lab)
    ax.axvline(r.cmc_mM, color=P.MARK, ls=":", lw=1.2, label=f"CMC = {r.cmc_mM:.3g} mM")
    ax.set_xlabel("Concentration (mM)"); ax.set_ylabel("Specific conductivity")
    ax.legend(fontsize=7, loc="best")
    return RunResult(values, [Figure("conductivity", P.to_png(fig), "Conductivity against concentration with the CMC.")],
                     conclusion, warnings,
                     {"cmc_mM_conductivity": r.cmc_mM, "beta": beta, "alpha": alpha,
                      "cmc_mM": r.cmc_mM, "cmc_source": "conductivity"},
                     ["curve_analysis.cmc_from_conductivity_curve"])


CMC_CONDUCTIVITY = Technique(
    id="cmc_conductivity", category="Micellization", title="CMC and counterion binding from conductivity",
    level="primary",
    summary="CMC and degree of counterion binding (beta) from a conductivity vs concentration curve "
            "(ionic surfactants only).",
    dataset=CONDUCTIVITY,
    methods=[Method("rss", "Two-line break point",
                    "Fits straight lines below and above the CMC and places the break where the total residual "
                    "is smallest; alpha is the ratio of the two slopes.",
                    "Standard for ionic surfactants. Nonionic surfactants give no usable conductivity break.")],
    run=run_conductivity, tools=["cmc_from_conductivity_curve", "counterion_binding_degree"],
    produces=["cmc_mM", "beta"],
    citations=["rosen_kunjappu_2012", "zana_1996"],
    unlocks=["gibbs_energy_micellization"],
    followups=["Use beta with the CMC to compute the free energy of micellization.",
               "Compare this CMC with the tensiometric CMC; agreement within about 10% is typical."],
    keywords=["conductivity", "conductometric", "counterion", "binding", "ionization", "beta", "alpha", "kappa"],
)


# --------------------------------------------------- free energy (derived)
def _factor(beta):
    return 1.0 if beta in (None, "") else 1.0 + float(beta)


def run_gibbs(inp: RunInput) -> RunResult:
    T = float(inp.params["temperature_K"])
    beta = inp.params.get("beta")
    if inp.method == "pseudo_phase_ionic" and beta in (None, ""):
        raise ValueError("Ionic surfactant: enter beta (run conductivity first, or use a literature value).")
    if inp.method == "pseudo_phase_nonionic":
        beta = None
    cmc = float(inp.session["cmc_mM"])
    x = th.cmc_to_mole_fraction(cmc / 1000.0)
    f = _factor(beta)
    dg = th.gibbs_free_energy_micellization(x, T, f)
    values = [Value("CMC used", cmc, "mM"), Value("CMC as mole fraction, X_cmc", x),
              Value("Factor (1 + beta)", f, sig=3),
              Value("Standard free energy of micellization", dg, "kJ/mol")]
    concl = [f"Micellization is spontaneous (Delta G_mic = {dg:.3g} kJ/mol)."]
    if beta not in (None, ""):
        concl.append(f"For this ionic surfactant the counterion binding (beta = {float(beta):.2f}) makes "
                     f"micellization {abs(dg) - abs(dg / f):.3g} kJ/mol more favourable than the nonionic form "
                     f"of the equation would suggest.")
    concl.append("Report it with the convention used: Delta G_mic = (1 + beta) RT ln X_cmc, CMC in mole fraction.")
    return RunResult(values, [], concl, [], {"delta_g_mic_kJ": dg},
                     ["thermodynamics.cmc_to_mole_fraction", "thermodynamics.gibbs_free_energy_micellization"])


GIBBS = Technique(
    id="gibbs_energy_micellization", category="Thermodynamics", title="Free energy of micellization",
    level="derived",
    summary="Standard Gibbs free energy of micellization from the CMC (and beta for ionic surfactants).",
    params=[TEMPERATURE, BETA],
    methods=[Method("pseudo_phase_nonionic", "Nonionic (phase separation)",
                    "Delta G_mic = RT ln X_cmc.", "Nonionic surfactants."),
             Method("pseudo_phase_ionic", "Ionic with counterion binding",
                    "Delta G_mic = (1 + beta) RT ln X_cmc: bound counterions leave the solution with the "
                    "surfactant and add to the free energy change.", "Ionic surfactants, with beta measured.")],
    requires=["cmc_mM"], run=run_gibbs,
    tools=["gibbs_free_energy_micellization", "cmc_to_mole_fraction"], citations=["zana_1996"],
    followups=["Measure the CMC at 3 or more temperatures to split Delta G into enthalpy and entropy."],
    keywords=["free energy", "gibbs energy", "delta g", "spontaneous", "thermodynamic"],
)


# -------------------------------------------------------- van't Hoff (primary)
def run_vant_hoff(inp: RunInput) -> RunResult:
    T, cmc = inp.data["T"], inp.data["cmc"]
    if len(T) < 3:
        raise ValueError("Need the CMC at 3 or more temperatures.")
    beta = inp.params.get("beta")
    f = _factor(beta)
    xs = [th.cmc_to_mole_fraction(c / 1000.0) for c in cmc]
    r = th.vant_hoff_multi_point_fit(xs, T, f)
    values = [Value("Enthalpy of micellization, Delta H", r.delta_H_kJ_per_mol, "kJ/mol"),
              Value("Entropy of micellization, Delta S", r.delta_S_J_per_mol_K, "J/(mol K)"),
              Value("Heat capacity change, Delta Cp", r.delta_Cp_J_per_mol_K, "J/(mol K)"),
              Value("Reference temperature", r.reference_temperature_K, "K"),
              Value("Fit R^2", r.r_squared), Value("Temperatures used", r.n_points),
              Value("Factor (1 + beta)", f, sig=3)]
    dh, ts = r.delta_H_kJ_per_mol, r.reference_temperature_K * r.delta_S_J_per_mol_K / 1000
    driver = "entropy-driven (hydrophobic effect dominates)" if abs(ts) > abs(dh) else "enthalpy-driven"
    concl = [f"At {r.reference_temperature_K:.1f} K micellization is {driver}: Delta H = {dh:.3g} kJ/mol, "
             f"T Delta S = {ts:.3g} kJ/mol.",
             f"Delta H is {'exothermic' if dh < 0 else 'endothermic'} at this temperature."]
    if r.delta_Cp_J_per_mol_K is not None and r.delta_Cp_J_per_mol_K < 0:
        concl.append("The negative Delta Cp is the usual signature of hydrophobic tails being removed from water.")
    warn = ["beta is assumed constant over the temperature range; if it changes with temperature, "
            "measure it at each temperature."] if beta not in (None, "") else []
    if len(T) < 5:
        warn.append("Fewer than 5 temperatures: Delta Cp is weakly determined.")
    fig, ax = P.new()
    inv = [1000.0 / t for t in T]
    import math
    ax.scatter(inv, [math.log(x) for x in xs], s=18, color=P.DATA, zorder=3, label="ln X_cmc")
    ax.set_xlabel("1000 / T (1/K)"); ax.set_ylabel("ln X_cmc"); ax.legend(fontsize=7, loc="best")
    return RunResult(values, [Figure("vant_hoff", P.to_png(fig), "ln X_cmc against inverse temperature.")],
                     concl, warn, {"delta_h_mic_kJ": dh}, ["thermodynamics.vant_hoff_multi_point_fit"])


VANT_HOFF_T = Technique(
    id="vant_hoff", category="Thermodynamics", title="Enthalpy and entropy of micellization (van't Hoff)",
    level="primary",
    summary="Delta H, Delta S and Delta Cp of micellization from the CMC measured at 3 or more temperatures.",
    dataset=VANT_HOFF, params=[BETA],
    methods=[Method("gibbs_helmholtz", "Multi-point Gibbs-Helmholtz fit",
                    "Fits Delta G(T) = (1 + beta) RT ln X_cmc across all temperatures for Delta H, Delta S and "
                    "Delta Cp together, instead of a two-point slope.", "3 or more temperatures; 5 or more recommended.")],
    run=run_vant_hoff, tools=["vant_hoff_multi_point_fit"], citations=["zana_1996"],
    followups=["Check enthalpy-entropy compensation if you have several surfactants or additives."],
    keywords=["van't hoff", "vant hoff", "enthalpy", "entropy", "temperature", "heat capacity", "thermodynamics"],
)

TECHNIQUES = [CMC_CONDUCTIVITY, GIBBS, VANT_HOFF_T]
