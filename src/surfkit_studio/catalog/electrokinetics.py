"""Zeta potential from electrophoretic mobility.

Measurement-level: one measured mobility plus the solution conditions. The
Debye length comes from the ionic strength, kappa*a from it and the particle
(micelle) radius, and the Henry function f(kappa*a) is taken from the regime
the researcher chooses; the full-range forms (Swan-Furst, Ohshima) are the
default because real micelles sit between the Hueckel and Smoluchowski limits.
"""
from __future__ import annotations

import math

from surfactantkit import electrostatics as E

from .. import plotting as P
from .base import Figure, Method, Param, RunInput, RunResult, Technique, Value

HENRY = {"swan_furst": "Henry, Swan-Furst", "ohshima": "Henry, Ohshima", "smoluchowski": "Smoluchowski limit",
         "huckel": "Hueckel limit"}


def _f_plot(ka: float):
    xs = [10 ** (i / 20) for i in range(-40, 61)]          # kappa*a from 0.01 to 1000
    fig, ax = P.new()
    ax.plot(xs, [E.henry_function("swan_furst", x) for x in xs], color=P.FIT, lw=1.5, label="Full range (Swan-Furst)")
    ax.plot(xs, [E.henry_function("ohshima", x) for x in xs], color=P.ALT, lw=1.0, ls="--", label="Ohshima")
    ax.axhline(1.0, color=P.MUTED, lw=0.8, ls=":")
    ax.axhline(1.5, color=P.MUTED, lw=0.8, ls=":")
    ax.text(xs[-1], 1.01, "Hueckel limit 1.0", fontsize=7, color=P.MUTED, va="bottom", ha="right")
    ax.text(xs[0], 1.49, "Smoluchowski limit 1.5", fontsize=7, color=P.MUTED, va="top")
    ax.axvline(ka, color=P.MARK, lw=1.2, label=f"Your sample, kappa a = {ka:.3g}")
    ax.set_xscale("log")
    ax.set_xlabel("kappa a"); ax.set_ylabel("Henry function f(kappa a)"); ax.legend(fontsize=7, loc="center left")
    return Figure("henry", P.to_png(fig), "Henry function against kappa a, with the sample's kappa a marked.")


def run_zeta(inp: RunInput) -> RunResult:
    p, method = inp.params, inp.method or "swan_furst"
    mu = float(p["mobility"])
    I, a = float(p["ionic_strength_M"]), float(p["radius_nm"])
    T = float(p.get("temperature_K") or 298.15)
    eta = float(p.get("viscosity_mPas") or 0.89)
    eps = float(p.get("rel_permittivity") or E.WATER_REL_PERMITTIVITY_25C)
    if a <= 0:
        raise ValueError("The particle or micelle radius must be positive.")
    lam = E.debye_length(I, T, eps)
    ka = a / lam
    calls = ["electrostatics.debye_length", "electrostatics.henry_function"]
    values = [Value("Debye length", lam, "nm", 3), Value("kappa a", ka, sig=3)]
    warn: list[str] = []

    def henry(regime):
        return E.zeta_potential_henry(mu, eta, regime, eps, ka), E.henry_function(regime, ka)

    def relax():
        if ka < 10:
            raise ValueError(f"The relaxation-corrected formula is valid for kappa a >= 10; this sample has kappa a = "
                             f"{ka:.3g}. Use a Henry method, or a full O'Brien-White numerical solution.")
        z = int(float(p.get("z") or 1))
        m = float(p.get("m_drag") or 0.15)
        return math.copysign(E.zeta_potential_relaxation_corrected(abs(mu), ka, eta, T, z, m, eps), mu)

    if method in HENRY:
        zeta, f = henry(method)
        calls.append("electrostatics.zeta_potential_henry")
        values += [Value("Henry function f(kappa a)", f, sig=4), Value("Zeta potential", zeta, "mV", 3)]
        f_full = E.henry_function("swan_furst", ka)
        if method in ("huckel", "smoluchowski") and abs(f / f_full - 1) > 0.05:
            warn.append(f"At kappa a = {ka:.3g} the {HENRY[method]} uses f = {f:g} where the full-range Henry "
                        f"function gives {f_full:.3f}; zeta is off by {100 * abs(f_full / f - 1):.0f}%. Use the "
                        "Swan-Furst or Ohshima method.")
    elif method == "relaxation":
        zeta = relax()
        calls.append("electrostatics.zeta_potential_relaxation_corrected")
        values.append(Value("Zeta potential (relaxation-corrected)", zeta, "mV", 3))
    elif method == "compare":
        rows = {}
        for reg in HENRY:
            rows[HENRY[reg]] = henry(reg)[0]
        calls.append("electrostatics.zeta_potential_henry")
        try:
            rows["Relaxation-corrected (OHW)"] = relax()
            calls.append("electrostatics.zeta_potential_relaxation_corrected")
        except ValueError as e:
            warn.append(f"Relaxation-corrected value not shown: {e}")
        values += [Value(f"Zeta, {k}", v, "mV", 3) for k, v in rows.items()]
        zeta = rows[HENRY["swan_furst"]]
        spread = max(rows.values()) - min(rows.values())
        values.append(Value("Spread between methods", spread, "mV", 3))
    else:
        raise ValueError(f"Unknown zeta-potential method {method!r}.")

    relaxed = method == "relaxation" or "electrostatics.zeta_potential_relaxation_corrected" in calls
    if abs(zeta) > 50 and not relaxed:
        warn.append("Above about 50 mV counterion relaxation makes mobility grow more slowly than the Henry equation "
                    "assumes, so the Henry zeta is too low in magnitude"
                    + ("; the relaxation-corrected method applies at this kappa a." if ka >= 10 else
                       "; at this kappa a only a full numerical (O'Brien-White) treatment corrects it."))
    sign = "positive" if zeta > 0 else "negative"
    concl = [f"Zeta potential {zeta:.3g} mV ({sign}) at kappa a = {ka:.3g} (Debye length {lam:.3g} nm).",
             f"The sign is the sign of the charge at the shear plane: for micelles it follows the head-group "
             "charge; for particles it shows which ionic surfactant has adsorbed.",
             "Electrostatic stabilisation is usually discussed in terms of the magnitude of zeta; a commonly quoted "
             "rule of thumb treats magnitudes above about 30 mV as well stabilised, but it ignores steric and van der "
             "Waals contributions and is not a criterion."]
    return RunResult(values, [_f_plot(ka)], concl, warn, {"zeta_mV": zeta, "kappa_a": ka}, calls)


ZETA = Technique(
    id="zeta_potential", category="Electrokinetics", title="Zeta potential from electrophoretic mobility",
    level="measurement",
    summary="Zeta potential from a measured electrophoretic mobility, with the Henry function chosen for the "
            "actual kappa a of your micelles or particles, and a relaxation-corrected option for high zeta.",
    params=[Param("mobility", "Electrophoretic mobility (with sign)", "float", "um cm/(V s)", None,
                  help="As reported by the instrument, e.g. -3.5. 1 um cm/(V s) = 1e-8 m^2/(V s)."),
            Param("ionic_strength_M", "Ionic strength", "float", "mol/L", None,
                  help="For a 1:1 salt this equals its concentration; include the surfactant's own free ions."),
            Param("radius_nm", "Particle or micelle radius", "float", "nm", None,
                  help="Hydrodynamic radius from DLS, or an estimate for micelles (about 2 to 4 nm)."),
            Param("temperature_K", "Temperature", "float", "K", 298.15, from_session="temperature_K"),
            Param("viscosity_mPas", "Solvent viscosity", "float", "mPa s", 0.89, help="Water at 25 C: 0.89."),
            Param("rel_permittivity", "Relative permittivity", "float", "", E.WATER_REL_PERMITTIVITY_25C,
                  help="Water at 25 C: 78.4; it falls with temperature."),
            Param("z", "Relaxation method: electrolyte charge number z", "float", "", 1, required=False),
            Param("m_drag", "Relaxation method: ionic drag coefficient m", "float", "", 0.15, required=False,
                  help="Dimensionless; about 0.18 for KCl at 25 C.")],
    methods=[Method("swan_furst", "Henry, Swan-Furst (full range)",
                    "Henry equation with a rational expression for f(kappa a) accurate to about 0.1% at any kappa a.",
                    "Default. Micelles and nanoparticles at ordinary ionic strengths, which lie between the two "
                    "classical limits."),
             Method("ohshima", "Henry, Ohshima (full range)",
                    "Henry equation with Ohshima's closed-form f(kappa a), accurate to about 1% at any kappa a.",
                    "Cross-check of the Swan-Furst result, or to match papers that used Ohshima."),
             Method("smoluchowski", "Smoluchowski limit",
                    "f = 1.5: thin double layer compared with the particle size.",
                    "Large particles at high ionic strength (kappa a above about 100); most instruments' default."),
             Method("huckel", "Hueckel limit", "f = 1.0: thick double layer compared with the particle size.",
                    "Very small particles in very dilute electrolyte (kappa a well below 1)."),
             Method("relaxation", "Relaxation-corrected (Ohshima-Healy-White)",
                    "Adds the polarisation (relaxation) of the double layer, which slows particles with high zeta.",
                    "High zeta (above about 50 mV) and kappa a of 10 or more."),
             Method("compare", "Compare all methods",
                    "Runs every applicable method and reports the spread.",
                    "To see how much the choice of model matters for your sample.")],
    run=run_zeta,
    tools=["debye_length", "zeta_potential_henry", "zeta_potential_relaxation_corrected"],
    citations=["swan_furst_2012", "ohshima_1994", "ohshima_healy_white_1983"],
    produces=["zeta_mV"],
    followups=["Measure zeta against added salt to see the double layer compress.",
               "For ionic surfactant adsorbed on particles, follow zeta against surfactant concentration to find "
               "charge neutralisation and reversal."],
    keywords=["zeta", "electrophoretic", "electrophoresis", "mobility", "henry function", "smoluchowski", "huckel",
              "debye length", "surface charge"],
)

TECHNIQUES = [ZETA]
