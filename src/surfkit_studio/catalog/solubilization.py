"""Micellar solubilization capacity.

Primary: total solubilized concentration of a sparingly soluble solute
against surfactant concentration. Above the CMC the line's slope is the
molar solubilization ratio (MSR); the micelle-water partition coefficient Km
follows on the mole-fraction basis (Edwards, Luthy and Liu 1991).
"""
from __future__ import annotations

import math
import statistics

from surfactantkit import solubilization as SOL

from .. import plotting as P
from .base import Column, DatasetSpec, Figure, Method, Param, RunInput, RunResult, Technique, Value

DATA = DatasetSpec(
    columns=[Column("conc", "Surfactant concentration", ["mM", "M", "uM"], ["surfactant", "conc", "concentration"]),
             Column("S", "Total solubilized solute", ["mM", "M", "uM"], ["solubilized", "solubility", "solute",
                                                                         "dissolved"])],
    min_rows=4, example="synthetic_solubilization.csv")

SOLUTES = [("other", "Other (enter its water solubility)")] + [
    (k, k.capitalize()) for k in SOL.INTRINSIC_WATER_SOLUBILITY_REFERENCE_M]


def run_solubilization(inp: RunInput) -> RunResult:
    c, S = inp.data["conc"], inp.data["S"]
    p, method = inp.params, inp.method or "slope"
    cmc = float(p["cmc_mM"])
    warn: list[str] = []
    sw = p.get("intrinsic_mM")
    solute = p.get("solute") or "other"
    if sw in (None, ""):
        ref = SOL.INTRINSIC_WATER_SOLUBILITY_REFERENCE_M.get(solute)
        if ref is None:
            raise ValueError("Enter the solute's water solubility (without surfactant), or pick a solute SurfactantKit "
                             "has a sourced value for.")
        sw = ref["solubility_M"] * 1000.0
        warn.append(f"Water solubility of {solute} taken from SurfactantKit's reference table ({sw:.3g} mM; "
                    f"{ref['confidence']} confidence: {ref['source']}).")
    sw = float(sw)
    pts = [(x, y) for x, y in zip(c, S) if x > cmc]
    if len(pts) < 3:
        raise ValueError(f"Need at least 3 points above the CMC ({cmc:g} mM) to define the solubilization line; "
                         f"found {len(pts)}.")
    xs, ys = [x for x, _ in pts], [y for _, y in pts]
    per_point = [SOL.molar_solubilization_ratio(y / 1000, sw / 1000, x / 1000, cmc / 1000) for x, y in pts]
    calls = ["solubilization.molar_solubilization_ratio"]
    fit = statistics.linear_regression(xs, ys)
    r2 = statistics.correlation(xs, ys) ** 2
    if method == "slope":
        msr = fit.slope
        basis = "slope of total solubilized against surfactant concentration above the CMC"
    elif method == "pointwise":
        msr = statistics.mean(per_point)
        basis = "mean of (S - S_w)/(C - CMC) over the points above the CMC"
    else:
        raise ValueError(f"Unknown solubilization method {method!r}.")
    if msr <= 0:
        raise ValueError("The solubilized amount does not rise above the CMC, so no solubilization capacity can be "
                         "derived; check the CMC and the units.")
    # Km on the mole-fraction basis needs only MSR and S_w: X_mic = MSR/(1+MSR), X_w = S_w/55.5 M
    km = SOL.micelle_water_partition_coefficient((sw + msr) / 1000, sw / 1000, (cmc + 1) / 1000, cmc / 1000)
    calls.append("solubilization.micelle_water_partition_coefficient")
    s_cmc_fit = fit.slope * cmc + fit.intercept

    fig, ax = P.new()
    ax.scatter(c, S, s=20, color=P.DATA, zorder=3, label="Measured")
    xl = [cmc, max(c)]
    ax.plot(xl, [fit.slope * x + fit.intercept for x in xl], color=P.FIT, lw=1.5, label="Linear fit above CMC")
    ax.axvline(cmc, color=P.MARK, lw=1.0, ls="--", label="CMC")
    ax.axhline(sw, color=P.MUTED, lw=0.8, ls=":", label="Water solubility")
    ax.set_xlabel("Surfactant concentration (mM)"); ax.set_ylabel("Total solubilized (mM)")
    ax.legend(fontsize=7, loc="best")

    values = [Value("Molar solubilization ratio, MSR", msr, sig=3), Value("MSR basis", basis),
              Value("Micelle-water partition coefficient, Km", km, sig=3),
              Value("log10 Km", math.log10(km), sig=3),
              Value("MSR spread over points (min to max)", f"{min(per_point):.3g} to {max(per_point):.3g}"),
              Value("R^2 of the line above the CMC", r2, sig=3),
              Value("Fitted solubility at the CMC", s_cmc_fit, "mM", 3)]
    if sw > 0 and abs(s_cmc_fit - sw) > 0.5 * sw:
        warn.append(f"The fitted line meets the CMC at {s_cmc_fit:.3g} mM, far from the water solubility "
                    f"({sw:.3g} mM). Either the CMC under these conditions differs (solutes often lower it) or the "
                    "first points above the CMC are not yet on the line.")
    if max(per_point) > 1.5 * min(per_point):
        warn.append(f"Point-by-point MSR ranges from {min(per_point):.3g} to {max(per_point):.3g}. Points just above "
                    "the CMC are the most sensitive to the CMC value used, so the slope method is the more robust "
                    "estimate; check that the CMC applies to these conditions.")
    warn.append("Km here is on the mole-fraction basis (X in micelle / X in water); some papers use a concentration "
                "ratio instead, which gives a different number for the same data.")
    concl = [f"Each mole of micellized surfactant takes up {msr:.3g} mol of solute"
             + (f", i.e. about {1 / msr:.3g} surfactant molecules per solubilized molecule." if msr < 1 else "."),
             f"The solute prefers the micelles over water by a factor Km = {km:.3g} (log Km {math.log10(km):.2f}) "
             "on a mole-fraction basis."]
    return RunResult(values, [Figure("solubilization", P.to_png(fig),
                                     "Total solubilized solute against surfactant concentration.")],
                     concl, warn, {"msr": msr, "km": km}, calls)


SOLUBILIZATION = Technique(
    id="solubilization", category="Solubilization", title="Solubilization capacity (MSR and Km)", level="primary",
    summary="Molar solubilization ratio and micelle-water partition coefficient from the solubility of a sparingly "
            "soluble solute measured at several surfactant concentrations.",
    dataset=DATA,
    params=[Param("cmc_mM", "CMC", "float", "mM", None, from_session="cmc_mM"),
            Param("solute", "Solute", "choice", "", "other", choices=SOLUTES, required=False),
            Param("intrinsic_mM", "Water solubility of the solute (no surfactant)", "float", "mM", None,
                  required=False, help="Leave empty to use SurfactantKit's sourced value for the chosen solute.")],
    methods=[Method("slope", "Slope above the CMC",
                    "Total solubilized rises linearly with micellized surfactant; the slope is the MSR.",
                    "Default. Uses all points above the CMC together and is insensitive to the exact CMC."),
             Method("pointwise", "Mean of point-by-point MSR",
                    "MSR = (S - S_w)/(C - CMC) at each concentration, averaged.",
                    "When only a few concentrations were measured, or to see whether MSR drifts with "
                    "concentration.")],
    run=run_solubilization,
    tools=["molar_solubilization_ratio", "micelle_water_partition_coefficient"],
    citations=["edwards_1991"], produces=["msr", "km"],
    followups=["Compare MSR across surfactants with the same solute to rank solubilizing power.",
               "A high Km with a low MSR suggests the solute sits at the micelle interface rather than the core."],
    keywords=["solubilization", "solubilisation", "solubilized", "msr", "partition coefficient", "naphthalene",
              "pyrene solubility", "hydrophobic solute"],
)

TECHNIQUES = [SOLUBILIZATION]
