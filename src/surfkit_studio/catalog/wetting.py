"""Wetting and solid surface energy.

Measurement-level: the researcher enters a few measured numbers (contact
angles, a surface tension), no curve is needed.
Solid surface energy by Owens-Wendt-Rabel-Kaelble (dispersive/polar) or van
Oss-Chaudhury-Good (Lifshitz-van der Waals/acid/base), using the toolkit's
table of the four standard probe liquids; wetting by a liquid (for example a
surfactant solution at its CMC) as work of adhesion and spreading coefficient.
"""
from __future__ import annotations

import math

from surfactantkit import wetting as W

from .. import plotting as P
from .base import Figure, Method, Param, RunInput, RunResult, Technique, Value

LIQUIDS = ["water", "diiodomethane", "glycerol", "formamide"]


def _angles(p: dict) -> dict[str, float]:
    out = {}
    for name in LIQUIDS:
        v = p.get(f"theta_{name}")
        if v not in (None, ""):
            v = float(v)
            if not 0.0 <= v <= 180.0:
                raise ValueError(f"The contact angle of {name} must be between 0 and 180 degrees.")
            out[name] = v
    return out


# ------------------------------------------------------- solid surface energy
def run_surface_energy(inp: RunInput) -> RunResult:
    method = inp.method or "owrk"
    th = _angles(inp.params)
    names = list(th)
    warn = ["Probe-liquid surface tension components are SurfactantKit's standard table for these four liquids; "
            "if the paper you compare against used different component values, the split will differ."]
    if method == "owrk":
        if len(names) < 2:
            raise ValueError("Owens-Wendt needs contact angles of at least two probe liquids, one of them mainly "
                             "dispersive (diiodomethane) and one polar (water).")
        comp = [W.get_owens_wendt_standard_liquid(n) for n in names]
        d = [c["dispersive"] for c in comp]
        pol = [c["polar"] for c in comp]
        r = W.owens_wendt_solid_surface_energy([th[n] for n in names], d, pol)
        sd, sp, st = r.gamma_s_dispersive_mN_m, r.gamma_s_polar_mN_m, r.gamma_s_total_mN_m
        xs = [math.sqrt(pp) / math.sqrt(dd) for dd, pp in zip(d, pol)]
        ys = [W.work_of_adhesion(dd + pp, th[n]) / (2 * math.sqrt(dd)) for n, dd, pp in zip(names, d, pol)]
        fig, ax = P.new()
        ax.scatter(xs, ys, s=24, color=P.DATA, zorder=3, label="Probe liquids")
        for n, x, y in zip(names, xs, ys):
            ax.annotate(n, (x, y), textcoords="offset points", xytext=(4, 4), fontsize=7, color=P.MUTED)
        x_line = [0.0, max(xs) * 1.1 or 1.0]
        ax.plot(x_line, [math.sqrt(sd) + math.sqrt(sp) * x for x in x_line], color=P.FIT, lw=1.5,
                label="OWRK fit")
        ax.set_xlabel("sqrt(gamma_L^p) / sqrt(gamma_L^d)")
        ax.set_ylabel("W_a / (2 sqrt(gamma_L^d))  (mN/m)^0.5")
        ax.margins(x=0.15, y=0.12)
        ax.legend(fontsize=7, loc="best")
        figs = [Figure("owrk", P.to_png(fig), "Owens-Wendt plot: intercept and slope give the square roots of the "
                                              "dispersive and polar surface energy.")]
        values = [Value("Total surface energy, gamma_S", st, "mN/m", 3),
                  Value("Dispersive component, gamma_S^d", sd, "mN/m", 3),
                  Value("Polar component, gamma_S^p", sp, "mN/m", 3),
                  Value("Probe liquids used", ", ".join(names))]
        if r.n_liquids >= 3:
            values.append(Value("R^2 of the OWRK line", r.r_squared, sig=3))
        else:
            warn.append("With two liquids the OWRK line passes exactly through both points; a third liquid gives a "
                        "real check (R^2) of the result.")
        if "diiodomethane" not in names:
            warn.append("No mainly dispersive liquid (diiodomethane) was used; the dispersive/polar split is poorly "
                        "conditioned without one.")
        calls = ["wetting.get_owens_wendt_standard_liquid", "wetting.owens_wendt_solid_surface_energy"]
        provides = {"gamma_s_total_mN_m": st, "gamma_s_dispersive_mN_m": sd, "gamma_s_polar_mN_m": sp}
        frac = sp / st if st > 0 else 0.0
        concl = [f"The solid's surface energy is {st:.3g} mN/m, {100 * frac:.0f}% of it polar "
                 f"({sp:.3g} mN/m) and the rest dispersive ({sd:.3g} mN/m).",
                 "A liquid wets this solid better the closer its own dispersive/polar make-up and total surface "
                 "tension are to the solid's."]
    elif method == "vocg":
        if len(names) != 3:
            raise ValueError("van Oss-Chaudhury-Good needs contact angles of exactly three probe liquids, normally "
                             "diiodomethane plus two polar liquids (water with glycerol or formamide).")
        comp = [W.get_vocg_standard_liquid(n) for n in names]
        r = W.van_oss_chaudhury_good_solid_surface_energy(
            [th[n] for n in names], [c["lw"] for c in comp], [c["acid"] for c in comp], [c["base"] for c in comp])
        st = r.gamma_s_total_mN_m
        ab = st - r.gamma_s_lw_mN_m
        values = [Value("Total surface energy, gamma_S", st, "mN/m", 3),
                  Value("Lifshitz-van der Waals component, gamma_S^LW", r.gamma_s_lw_mN_m, "mN/m", 3),
                  Value("Electron-acceptor (acid) parameter, gamma_S^+", r.gamma_s_acid_mN_m, "mN/m", 3),
                  Value("Electron-donor (base) parameter, gamma_S^-", r.gamma_s_base_mN_m, "mN/m", 3),
                  Value("Acid-base component, 2 sqrt(gamma+ gamma-)", ab, "mN/m", 3),
                  Value("Probe liquids used", ", ".join(names))]
        figs = []
        calls = ["wetting.get_vocg_standard_liquid", "wetting.van_oss_chaudhury_good_solid_surface_energy"]
        provides = {"gamma_s_total_mN_m": st}
        side = ("electron-donor (basic)" if r.gamma_s_base_mN_m > r.gamma_s_acid_mN_m
                else "electron-acceptor (acidic)")
        concl = [f"The solid's surface energy is {st:.3g} mN/m: {r.gamma_s_lw_mN_m:.3g} mN/m Lifshitz-van der "
                 f"Waals and {ab:.3g} mN/m acid-base.",
                 f"Its polar character is mainly {side}. Three liquids give an exact solve, so this split has no "
                 "internal error estimate; repeat with a different polar pair to check it."]
        if "diiodomethane" not in names:
            warn.append("Without diiodomethane (purely Lifshitz-van der Waals) the three equations are nearly "
                        "dependent and the acid/base split is unreliable.")
    else:
        raise ValueError(f"Unknown surface-energy method {method!r}.")
    return RunResult(values, figs, concl, warn, provides, calls)


def _theta(name: str) -> Param:
    return Param(f"theta_{name}", f"Contact angle of {name}", "float", "deg", None, required=False,
                 help="Leave empty if not measured.")


SURFACE_ENERGY = Technique(
    id="surface_energy", category="Wetting and surfaces", title="Solid surface energy from contact angles",
    level="measurement",
    summary="Surface energy of a solid and its dispersive/polar (OWRK) or Lifshitz-van der Waals/acid/base (van "
            "Oss-Chaudhury-Good) components, from contact angles of standard probe liquids.",
    params=[_theta(n) for n in LIQUIDS],
    methods=[Method("owrk", "Owens-Wendt-Rabel-Kaelble",
                    "Each liquid's work of adhesion is split into dispersive and polar geometric-mean terms; a "
                    "straight line through the liquids gives both components of the solid.",
                    "The usual choice; two liquids minimum, three or more give a real goodness of fit."),
             Method("vocg", "van Oss-Chaudhury-Good (acid-base)",
                    "Splits the polar part into electron-acceptor and electron-donor parameters; three liquids "
                    "give three equations for three unknowns.",
                    "When the acidic or basic character of the surface matters (adhesion, protein or polymer "
                    "interactions). Needs exactly three liquids, one apolar.")],
    run=run_surface_energy,
    tools=["owens_wendt_solid_surface_energy", "van_oss_chaudhury_good_solid_surface_energy"],
    citations=["owens_wendt_1969", "van_oss_1988"], produces=["gamma_s_total_mN_m"],
    unlocks=["wetting_solution"],
    followups=["Measure the contact angle of your surfactant solution on this solid to see how well it wets.",
               "Compare surfaces before and after a treatment by their polar component."],
    keywords=["surface energy", "surface free energy", "owens", "wendt", "owrk", "van oss", "acid-base",
              "diiodomethane", "probe liquid", "dispersive", "polar component"],
)


# ------------------------------------------------------- wetting by a liquid
def run_wetting(inp: RunInput) -> RunResult:
    p = inp.params
    g, th = float(p["gamma_lv_mN_m"]), float(p["theta_deg"])
    wa = W.work_of_adhesion(g, th)
    s = W.spreading_coefficient(g, th)
    wc = 2 * g
    if th == 0:
        state = "spreads completely (contact angle zero)"
    elif th < 90:
        state = "partially wets the solid (contact angle below 90 degrees)"
    else:
        state = "does not wet the solid (contact angle above 90 degrees)"
    concl = [f"The liquid {state}.",
             f"It adheres to the solid with {wa:.3g} mN/m against a cohesion of {wc:.3g} mN/m; the spreading "
             f"coefficient (adhesion minus cohesion) is {s:.3g} mN/m. The closer it is to zero, the closer the "
             "liquid is to spreading."]
    warn = ["The spreading coefficient here is computed from the measured contact angle (Young), so it can never be "
            "positive; a liquid that truly spreads shows a contact angle of zero and a positive spreading tendency "
            "this calculation cannot resolve."]
    if p.get("theta_kind") == "advancing":
        warn.append("Young's equation assumes an equilibrium angle; advancing angles overstate it on rough or "
                    "chemically patchy surfaces.")
    return RunResult([Value("Work of adhesion, W_a", wa, "mN/m", 3), Value("Work of cohesion, W_c = 2 gamma", wc,
                                                                            "mN/m", 3),
                      Value("Spreading coefficient, S", s, "mN/m", 3), Value("cos(theta)", math.cos(math.radians(th)),
                                                                             sig=3)],
                     [], concl, warn, {"work_of_adhesion_mN_m": wa, "spreading_coefficient_mN_m": s},
                     ["wetting.work_of_adhesion", "wetting.spreading_coefficient"])


WETTING = Technique(
    id="wetting_solution", category="Wetting and surfaces", title="Wetting: work of adhesion and spreading",
    level="measurement",
    summary="How well a liquid (for example your surfactant solution) wets a solid: work of adhesion and "
            "spreading coefficient from its surface tension and contact angle.",
    params=[Param("gamma_lv_mN_m", "Surface tension of the liquid", "float", "mN/m", None,
                  from_session="gamma_cmc_mN_m", help="Prefilled with the surface tension at the CMC if you ran a "
                                                      "tensiometry analysis."),
            Param("theta_deg", "Contact angle on the solid", "float", "deg", None),
            Param("theta_kind", "Type of contact angle", "choice", "", "static",
                  choices=[("static", "Static / equilibrium"), ("advancing", "Advancing"),
                           ("receding", "Receding")], required=False)],
    methods=[Method("young_dupre", "Young-Dupre",
                    "Work of adhesion W_a = gamma (1 + cos theta); spreading coefficient S = W_a - 2 gamma.",
                    "Any liquid with a measured surface tension and contact angle.")],
    run=run_wetting, tools=["work_of_adhesion", "spreading_coefficient"], citations=["rosen_kunjappu_2012"],
    produces=["work_of_adhesion_mN_m"],
    followups=["Repeat at several surfactant concentrations to find where wetting stops improving (usually near "
               "the CMC).",
               "Characterise the solid itself from probe-liquid contact angles (surface energy)."],
    keywords=["contact angle", "wetting", "wettability", "spreading", "work of adhesion", "adhesion", "young"],
)

TECHNIQUES = [SURFACE_ENERGY, WETTING]
