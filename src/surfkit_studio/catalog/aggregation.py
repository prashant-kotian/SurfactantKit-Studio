"""Micelle size and shape.

Primary: aggregation number from steady-state fluorescence quenching
(Turro-Yekta) and from a static light scattering Debye plot.
Derived: critical packing parameter and expected morphology from the
interfacial area per molecule (Gibbs A_min) and the tail length (Tanford).
"""
from __future__ import annotations

import math

from surfactantkit import cpp as C
from surfactantkit import curve_analysis as ca

from .. import plotting as P
from .base import Column, DatasetSpec, Figure, Method, Param, RunInput, RunResult, Technique, Value

QUENCH = DatasetSpec(
    columns=[Column("q", "Quencher concentration", ["mM", "M", "uM"], ["quencher", "[q]", "conc"]),
             Column("I", "Fluorescence intensity", ["a.u."], ["intensity", "fluorescence", "counts"])],
    min_rows=4, example="synthetic_quenching.csv")

SLS = DatasetSpec(
    columns=[Column("c", "Micellized concentration (C - CMC)", ["g/mL"], ["conc", "c-cmc", "g/ml"]),
             Column("R", "Excess Rayleigh ratio", ["1/cm"], ["rayleigh", "ratio", "delta r", "cm"])],
    min_rows=4, example="synthetic_sls.csv")


# --------------------------------------------------------- quenching (primary)
def run_quench(inp: RunInput) -> RunResult:
    q, I = inp.data["q"], inp.data["I"]
    p = inp.params
    I0, Ct, cmc = float(p["I0"]), float(p["total_surfactant_mM"]), float(p["cmc_mM"])
    if Ct <= cmc:
        raise ValueError("The total surfactant concentration must be above the CMC for micelles to exist.")
    r = ca.aggregation_number_from_quenching_curve(q, I, I0, Ct, cmc)
    N = r.aggregation_number
    xs = [0.0] + list(q)
    ys = [0.0] + [math.log(I0 / i) for i in I]
    fig, ax = P.new()
    ax.scatter(q, ys[1:], s=20, color=P.DATA, zorder=3, label="ln(I0/I)")
    ax.plot([0, max(q)], [0, r.slope_per_Q * max(q)], color=P.FIT, lw=1.5, label="Fit through origin")
    ax.set_xlabel("Quencher concentration (mM)"); ax.set_ylabel("ln(I0 / I)"); ax.legend(fontsize=7, loc="best")
    warn = []
    if max(ys[1:]) > 2.5:
        warn.append("ln(I0/I) exceeds about 2.5: at high quencher occupancy the Poisson assumption weakens and N "
                    "can be underestimated; keep quencher-to-micelle ratios low.")
    concl = [f"Each micelle contains about {N:.0f} surfactant molecules (aggregation number from steady-state "
             f"quenching).",
             "The method assumes the probe and quencher sit only in micelles and are Poisson-distributed among "
             "them; it measures the number-average N of the micelles present at this concentration."]
    return RunResult([Value("Aggregation number N", N, sig=3), Value("Slope of ln(I0/I) vs [Q]", r.slope_per_Q, "1/mM"),
                      Value("Micellized surfactant (Ct - CMC)", Ct - cmc, "mM")],
                     [Figure("quenching", P.to_png(fig), "Turro-Yekta plot of ln(I0/I) against quencher concentration.")],
                     concl, warn, {"aggregation_number": N}, ["curve_analysis.aggregation_number_from_quenching_curve"])


QUENCHING = Technique(
    id="aggregation_quenching", category="Micelle size and shape", title="Aggregation number by fluorescence quenching",
    level="primary",
    summary="Number of surfactant molecules per micelle from a steady-state fluorescence quenching series "
            "(Turro-Yekta method).",
    dataset=QUENCH,
    params=[Param("I0", "Intensity without quencher, I0", "float", "a.u.", None),
            Param("total_surfactant_mM", "Total surfactant concentration, Ct", "float", "mM", None),
            Param("cmc_mM", "CMC", "float", "mM", None, from_session="cmc_mM")],
    methods=[Method("turro_yekta", "Turro-Yekta",
                    "ln(I0/I) = N [Q] / (Ct - CMC): the slope of ln(I0/I) against quencher concentration gives N.",
                    "Steady-state fluorescence with a probe (e.g. pyrene) and a micelle-bound quencher.")],
    run=run_quench, tools=["aggregation_number_from_quenching_curve"], citations=["turro_yekta_1978"],
    produces=["aggregation_number"],
    followups=["Compare N with the value implied by the packing parameter (spherical micelles of this tail length).",
               "Repeat at several surfactant concentrations to see whether micelles grow."],
    keywords=["aggregation number", "quenching", "pyrene", "fluorescence", "turro", "nagg", "micelle size"],
)


# ---------------------------------------------------------------- SLS (primary)
def run_sls(inp: RunInput) -> RunResult:
    c, R = inp.data["c"], inp.data["R"]
    p = inp.params
    r = ca.aggregation_number_from_sls_debye_plot(c, R, float(p["dn_dc"]), float(p["wavelength_nm"]),
                                                   float(p["monomer_mw"]), float(p["n_solvent"]))
    lam = float(p["wavelength_nm"]) * 1e-7
    K = 4 * math.pi ** 2 * float(p["n_solvent"]) ** 2 * float(p["dn_dc"]) ** 2 / (6.02214076e23 * lam ** 4)
    fig, ax = P.new()
    ax.scatter(c, [K * x / y for x, y in zip(c, R)], s=20, color=P.DATA, zorder=3, label="K c / Delta R")
    xs = [0, max(c)]
    ax.plot(xs, [1 / r.micelle_molar_mass_g_per_mol + 2 * r.second_virial_coefficient_cm3_mol_per_g2 * x for x in xs],
            color=P.FIT, lw=1.5, label="Debye fit")
    ax.set_xlabel("Micellized concentration (g/mL)"); ax.set_ylabel("K c / Delta R (mol/g)"); ax.legend(fontsize=7, loc="best")
    A2 = r.second_virial_coefficient_cm3_mol_per_g2
    concl = [f"Micelle molar mass about {r.micelle_molar_mass_g_per_mol:.3g} g/mol, i.e. about "
             f"{r.aggregation_number:.0f} molecules per micelle.",
             ("A positive second virial coefficient means micelles repel each other (electrostatic or excluded-volume "
              "repulsion)." if A2 > 0 else "A negative second virial coefficient means net attraction between micelles.")]
    return RunResult([Value("Aggregation number N", r.aggregation_number, sig=3),
                      Value("Micelle molar mass", r.micelle_molar_mass_g_per_mol, "g/mol"),
                      Value("Second virial coefficient A2", A2, "cm^3 mol/g^2")],
                     [Figure("sls", P.to_png(fig), "Debye plot of K c / Delta R against micellized concentration.")],
                     concl, ["Assumes small micelles (radius of gyration below about 12 nm) so no angular correction is "
                             "needed; use the concentration above the CMC (C - CMC), not total concentration."],
                     {"aggregation_number": r.aggregation_number}, ["curve_analysis.aggregation_number_from_sls_debye_plot"])


SLS_T = Technique(
    id="aggregation_sls", category="Micelle size and shape", title="Aggregation number by static light scattering",
    level="primary",
    summary="Micelle molar mass, aggregation number and second virial coefficient from a Debye plot.",
    dataset=SLS,
    params=[Param("dn_dc", "Refractive index increment dn/dc", "float", "mL/g", None),
            Param("wavelength_nm", "Laser wavelength", "float", "nm", 632.8),
            Param("monomer_mw", "Monomer molar mass", "float", "g/mol", None),
            Param("n_solvent", "Solvent refractive index", "float", "", 1.333)],
    methods=[Method("debye", "Debye plot",
                    "K c / Delta R = 1/Mw + 2 A2 c; the intercept gives the micelle molar mass, the slope A2.",
                    "Single-angle SLS of small micelles.")],
    run=run_sls, tools=["aggregation_number_from_sls_debye_plot"], citations=["rosen_kunjappu_2012"],
    produces=["aggregation_number"],
    followups=["Compare with the fluorescence-quenching aggregation number if you have both."],
    keywords=["light scattering", "sls", "debye plot", "rayleigh", "molar mass of micelle", "virial"],
)


# ------------------------------------------------------- packing (derived)
def run_cpp(inp: RunInput) -> RunResult:
    n = int(float(inp.params["n_carbons"]))
    a0 = float(inp.session["a_min_nm2"]) * 100.0          # nm^2 -> A^2
    v = C.tanford_tail_volume(n)
    lc = C.tanford_critical_length(n)
    p = C.critical_packing_parameter(v, a0, lc)
    morph = C.classify_aggregate_morphology(p)
    concl = [f"Packing parameter {p:.2f}: expected aggregate shape is {morph}.",
             "Uses the area per molecule at the air-water interface as the head-group area; in micelles the "
             "effective head-group area is often larger, so treat the shape as a guide, not a measurement."]
    return RunResult([Value("Tail volume v (Tanford)", v, "A^3"), Value("Critical tail length lc (Tanford)", lc, "A"),
                      Value("Head-group area a0 (from A_min)", a0, "A^2"), Value("Packing parameter v/(a0 lc)", p, sig=3),
                      Value("Expected morphology", morph)], [], concl, [],
                     {"cpp": p, "morphology": morph},
                     ["cpp.tanford_tail_volume", "cpp.tanford_critical_length", "cpp.critical_packing_parameter",
                      "cpp.classify_aggregate_morphology"])


PACKING = Technique(
    id="packing_parameter", category="Micelle size and shape", title="Packing parameter and micelle shape",
    level="derived",
    summary="Critical packing parameter v/(a0 lc) and the expected aggregate shape (sphere, rod, bilayer).",
    params=[Param("n_carbons", "Carbons in the alkyl tail", "float", "", 12,
                  help="Saturated, unbranched chain length (e.g. 12 for SDS).")],
    methods=[Method("israelachvili", "Israelachvili packing",
                    "Tanford tail volume and length with the head-group area; thresholds 1/3, 1/2 and 1 separate "
                    "spheres, rods, bilayers and inverted phases.", "Single-tail surfactants with a known A_min.")],
    requires=["a_min_nm2"], run=run_cpp,
    tools=["tanford_tail_volume", "tanford_critical_length", "critical_packing_parameter", "classify_aggregate_morphology"],
    citations=["israelachvili_1976", "tanford_1972"],
    followups=["Check the predicted shape against an aggregation number or DLS size."],
    keywords=["packing parameter", "cpp", "morphology", "micelle shape", "spherical", "rod", "vesicle", "israelachvili"],
)

TECHNIQUES = [QUENCHING, SLS_T, PACKING]
