"""Dynamic surface tension: how fast a surfactant reaches a fresh interface.

Primary: surface tension against surface age (maximum bubble pressure, pendant
drop growth). Empirical Rosen-Hua characterisation, diffusion- vs
kinetically-limited regime selection (Ritacco et al. asymptotes), or a full
Ward-Tordai diffusion-adsorption fit giving D, K and Gamma_max.
"""
from __future__ import annotations

import math

from surfactantkit import dynamic_surface_tension as DST
from surfactantkit import dynamic_tension as WT

from .. import plotting as P
from .base import Column, DatasetSpec, Figure, Method, Param, RunInput, RunResult, Technique, Value
from .tensiometry import SYSTEM, SYSTEM_TYPES, TEMPERATURE

DATA = DatasetSpec(
    columns=[Column("t", "Surface age", ["s", "ms"], ["age", "time", "surface age", "bubble"],
                    factors={"s": 1.0, "ms": 0.001}),
             Column("gamma", "Dynamic surface tension", ["mN/m", "dyn/cm"], ["tension", "gamma", "sft", "dst"])],
    min_rows=6, example="synthetic_dynamic_tension.csv")

N_FACTOR = {"nonionic": 1.0, "ionic_excess_electrolyte": 1.0, "ionic_no_added_salt": 2.0}


def _plot(t, g, curves, gamma0):
    fig, ax = P.new()
    ax.scatter(t, g, s=18, color=P.DATA, zorder=3, label="Measured")
    for (xs, ys, label, color, ls) in curves:
        ax.plot(xs, ys, color=color, lw=1.5, ls=ls, label=label)
    ax.axhline(gamma0, color=P.MUTED, lw=0.8, ls=":")
    ax.set_xscale("log"); ax.set_xlabel("Surface age (s)"); ax.set_ylabel("Surface tension (mN/m)")
    ax.legend(fontsize=7, loc="best")
    return P.to_png(fig)


def _grid(t):
    lo, hi = math.log10(min(t)), math.log10(max(t))
    return [10 ** (lo + (hi - lo) * i / 120) for i in range(121)]


def run_dst(inp: RunInput) -> RunResult:
    t, g = inp.data["t"], inp.data["gamma"]
    p, method = inp.params, inp.method or "rosen_hua"
    gamma0 = float(p.get("gamma0_mN_m") or 72.0)
    if any(x <= 0 for x in t):
        raise ValueError("Surface ages must be positive.")
    if any(x >= gamma0 for x in g):
        raise ValueError(f"Every tension must be below gamma0 = {gamma0:g} mN/m (adsorption only lowers it); "
                         "check gamma0 and the units.")
    warn: list[str] = ["Surface age must be the true (corrected) surface age; raw bubble lifetimes from a maximum "
                       "bubble pressure tensiometer usually need the instrument's own dead-time correction."]
    span = max(g) - min(g)
    if span < 3.0:
        warn.append(f"The tension changes by only {span:.2g} mN/m over the measured ages: adsorption is almost "
                    "complete before the first point (or not started by the last), so the kinetic parameters are "
                    "poorly determined. Measure shorter (or longer) surface ages.")
    if method == "rosen_hua":
        r = DST.fit_rosen_hua(t, g, gamma0)
        xs = _grid(t)
        ys = [r.gamma_mesoequilibrium_mN_m + (gamma0 - r.gamma_mesoequilibrium_mN_m) /
              (1 + (x / r.t_star_s) ** r.n_exponent) for x in xs]
        figs = [Figure("dst", _plot(t, g, [(xs, ys, "Rosen-Hua fit", P.FIT, "-")], gamma0),
                       "Dynamic surface tension against surface age with the Rosen-Hua fit.")]
        values = [Value("Meso-equilibrium tension, gamma_m", r.gamma_mesoequilibrium_mN_m, "mN/m", 4),
                  Value("Characteristic time t* (half the drop)", r.t_star_s, "s", 3),
                  Value("Exponent n", r.n_exponent, sig=3), Value("R^2", r.r_squared, sig=4),
                  Value("Rate of drop at t*, (gamma0 - gamma_m) n / (4 t*)",
                        (gamma0 - r.gamma_mesoequilibrium_mN_m) * r.n_exponent / (4 * r.t_star_s), "mN/m per s", 3)]
        concl = [f"Half of the total tension drop is reached after t* = {r.t_star_s:.3g} s; the tension levels off "
                 f"near {r.gamma_mesoequilibrium_mN_m:.3g} mN/m.",
                 "A smaller t* means the surfactant covers new surface faster, which matters for fast processes "
                 "(spraying, foaming, printing, wetting of moving surfaces). Compare t* only at equal concentration "
                 "and temperature."]
        provides = {"dst_t_star_s": r.t_star_s}
        calls = ["dynamic_surface_tension.fit_rosen_hua"]
    elif method == "regime":
        r = DST.select_dst_kinetic_regime(t, g, gamma0)
        d = r.dla_fit
        xs = [x for x in _grid(t) if x > d.tau_d_s]
        ys = [gamma0 - d.delta_gamma_eq_mN_m * (1 - math.sqrt(d.tau_d_s / x)) for x in xs]
        figs = [Figure("dst", _plot(t, g, [(xs, ys, "Diffusion-limited fit", P.FIT, "-")], gamma0),
                       "Dynamic surface tension with the diffusion-limited asymptote.")]
        values = [Value("Selected regime", "diffusion-limited only" if r.selected_regime == "dla_only"
                        else "diffusion then kinetically limited"),
                  Value("Diffusion time tau_d", d.tau_d_s, "s", 3),
                  Value("Equilibrium tension drop (diffusion fit)", d.delta_gamma_eq_mN_m, "mN/m", 3),
                  Value("R^2 (diffusion-limited fit)", d.r_squared, sig=4)]
        if r.kla_fit is not None:
            values += [Value("Kinetic time tau_k", r.kla_fit.tau_k_s, "s", 3),
                       Value("Delta BIC (diffusion-only minus combined)", r.delta_bic, sig=3)]
        concl = [r.interpretation]
        if d.gap:
            warn.append(d.gap)
        provides = {"dst_tau_d_s": d.tau_d_s}
        calls = ["dynamic_surface_tension.select_dst_kinetic_regime", "dynamic_surface_tension.fit_dla_regime"]
    elif method == "ward_tordai":
        c0 = p.get("c0_mM")
        if c0 in (None, ""):
            raise ValueError("The Ward-Tordai fit needs the bulk surfactant concentration of this measurement.")
        st = p.get("system_type")
        if st not in N_FACTOR:
            raise ValueError("Choose the surfactant / electrolyte condition (it sets the Gibbs prefactor n).")
        fix_gm = p.get("gamma_max_source") == "session" and inp.session.get("gamma_max_mol_m2")
        p0 = (6e-11, 500.0, float(inp.session["gamma_max_mol_m2"]) if fix_gm else 4.0e-6, 0.5)
        r = WT.dynamic_surface_tension_ode(t, g, float(c0) / 1000.0, gamma0, N_FACTOR[st],
                                           float(p.get("temperature_K") or 298.15), p0=p0, fit_gamma_max=not fix_gm)
        figs = [Figure("dst", _plot(t, g, [(t, r.fitted_gamma_mN_per_m, "Ward-Tordai fit", P.FIT, "-")], gamma0),
                       "Dynamic surface tension with the diffusion-adsorption (Ward-Tordai) fit.")]
        values = [Value("Diffusion coefficient D", r.D_m2_per_s, "m^2/s", 3),
                  Value("D standard error", r.D_sd, "m^2/s", 2),
                  Value("Langmuir K", r.K_per_M, "1/M", 3), Value("K standard error", r.K_sd, "1/M", 2),
                  Value("Gamma_max", r.gamma_max_mol_per_m2, "mol/m^2", 3),
                  Value("Gamma_max " + ("(fixed from surface excess)" if fix_gm else "standard error"),
                        None if fix_gm else r.gamma_max_sd, "mol/m^2", 2),
                  Value("R^2", r.r_squared, sig=4), Value("RMS residual", r.rmse_mN_per_m, "mN/m", 3)]
        concl = [f"Diffusion coefficient {r.D_m2_per_s:.3g} m^2/s from the dynamic curve alone.",
                 "Typical surfactant monomers diffuse at a few times 1e-10 m^2/s; a much smaller apparent D "
                 "points to an adsorption barrier (kinetic control) rather than slow diffusion."]
        warn.append(r.caveat)
        if not r.converged:
            warn.append("The fit did not converge; treat the parameters as unreliable.")
        provides = {"dst_D_m2_s": r.D_m2_per_s}
        calls = ["dynamic_tension.dynamic_surface_tension_ode"]
    else:
        raise ValueError(f"Unknown method {method!r}.")
    return RunResult(values, figs, concl, warn, provides, calls)


DYNAMIC = Technique(
    id="dynamic_tension", category="Dynamic surface tension", title="Dynamic surface tension", level="primary",
    summary="How fast the surfactant lowers the tension of a fresh surface: Rosen-Hua t*, diffusion vs kinetic "
            "control, or a full Ward-Tordai fit for the diffusion coefficient.",
    dataset=DATA,
    params=[Param("gamma0_mN_m", "Tension of the fresh interface, gamma0", "float", "mN/m", 72.0,
                  help="Pure water against air: about 72 mN/m at 25 C."),
            TEMPERATURE,
            Param("c0_mM", "Ward-Tordai: bulk surfactant concentration", "float", "mM", None, required=False),
            Param("system_type", "Ward-Tordai: surfactant / electrolyte condition", "choice", "", None,
                  choices=SYSTEM_TYPES, required=False, from_session="system_type", help=SYSTEM.help),
            Param("gamma_max_source", "Ward-Tordai: Gamma_max", "choice", "", "fit",
                  choices=[("fit", "Fit it from this curve"),
                           ("session", "Fix it to the surface-excess result")], required=False)],
    methods=[Method("rosen_hua", "Rosen-Hua (empirical)",
                    "gamma(t) = gamma_m + (gamma0 - gamma_m) / (1 + (t/t*)^n): t* is the time to half the "
                    "drop, n the steepness.", "Default. Comparing how fast different surfactants act."),
             Method("regime", "Diffusion vs kinetic control",
                    "Fits the long-time diffusion-limited asymptote of Ward-Tordai, then tests by BIC whether a "
                    "second, kinetically limited stage is needed.",
                    "To decide whether adsorption is limited by diffusion or by an adsorption barrier."),
             Method("ward_tordai", "Ward-Tordai fit (D, K, Gamma_max)",
                    "Solves diffusion to the interface with Langmuir adsorption and fits D, K and Gamma_max "
                    "to the whole curve.", "Below the CMC, when the bulk concentration is known.")],
    run=run_dst, tools=["fit_rosen_hua", "select_dst_kinetic_regime", "dynamic_surface_tension_ode"],
    citations=["hua_rosen_1988", "ward_tordai_1946", "ritacco_2011"], produces=["dst_t_star_s"],
    followups=["Repeat at several concentrations: t* should fall as concentration rises.",
               "Fast adsorption (small t*) usually goes with good foamability; check with a foam test."],
    keywords=["dynamic surface tension", "bubble pressure", "surface age", "adsorption kinetics", "ward-tordai",
              "ward tordai", "rosen-hua", "dst"],
)

TECHNIQUES = [DYNAMIC]
