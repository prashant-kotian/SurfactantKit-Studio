"""Every result of a filled workbook, computed with SurfactantKit's own functions.

Order follows how the science builds up: pure surfactants (CMC, adsorption, counterion binding,
free energies), then the mixed micelle (Rubingh beta^M), then the mixed monolayer (Rosen
beta^sigma at a common surface tension), then Rosen's three synergism tests, then the optional
temperature series. Nothing is rounded here; rounding is display-only, in the writer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from surfactantkit import adsorption as ads
from surfactantkit import curve_analysis as ca
from surfactantkit import mixed_micelle as mm
from surfactantkit import thermodynamics as td
from surfactantkit.mixture_model_selection import rubingh_predict_cmc_mix, select_mixture_model

from .reader import Dataset, Study

R_GAS = 8.314462618
MIN_TENSION_POINTS = 6
MIN_COND_POINTS = 6


@dataclass
class Flag:
    where: str
    message: str
    level: str = "warning"          # "warning": affects a result; "note": for information


@dataclass
class Curve:
    """Results of one data sheet (pure or mixture)."""
    sheet: str
    alpha1: float | None
    t: object | None = None         # CmcFromCurveResult
    k: object | None = None         # CmcFromConductivityResult
    c_ref: float | None = None      # concentration at the Rosen reference surface tension (mM)
    extra: dict = field(default_factory=dict)


@dataclass
class Results:
    info: dict
    temperature_K: float
    gamma_ref: float
    curves: dict[str, Curve]
    pure: list[dict]
    mix_rows: list[dict]
    rubingh: dict
    rosen: dict
    synergism: list[dict]
    temperature: list[dict]
    flags: list[Flag]
    calls: list[str]


def _system_type(kind: str, salt_mM: float) -> str:
    if kind == "ionic":
        return "ionic_excess_electrolyte" if salt_mM > 0 else "ionic_no_added_salt"
    return "nonionic"


def _tension(ds: Dataset, flags: list[Flag], gamma_solvent: float) -> object | None:
    if not ds.tension:
        return None
    t = ds.tension
    if len(t.conc) < MIN_TENSION_POINTS:
        flags.append(Flag(ds.sheet, f"Only {len(t.conc)} surface tension points; at least {MIN_TENSION_POINTS} "
                                    "are needed for a CMC. Not analysed."))
        return None
    r = ca.cmc_from_surface_tension_curve(t.conc, t.mean)
    if ca.plateau_is_statistically_suspect(r):
        flags.append(Flag(ds.sheet, "The plateau above the CMC has too few points or is not flat; the CMC is "
                                    "provisional. Measure more concentrations above the break."))
    if r.n_premicellar_points < 3:
        flags.append(Flag(ds.sheet, f"The decline before the CMC has only {r.n_premicellar_points} points, so its "
                                    "slope (used for Gamma_max, A_min and Rosen beta-sigma) is not constrained."))
    unreliable = False
    if r.gamma0_mN_m - r.gamma_at_cmc_mN_per_m < 5.0:
        unreliable = True
        flags.append(Flag(ds.sheet, f"The fit finds almost no surface tension decline before the CMC "
                                    f"({r.gamma0_mN_m:.1f} to {r.gamma_at_cmc_mN_per_m:.1f} mN/m), so this CMC "
                                    f"({r.cmc_mM:.3g} mM) is not reliable. Measure concentrations through the decline."))
    # a drop of more than 15 mN/m between two neighbouring points is a step, not a curve
    for i in range(1, len(t.conc)):
        if t.mean[i - 1] - t.mean[i] > 15:
            unreliable = True
            flags.append(Flag(ds.sheet, f"Surface tension falls {t.mean[i - 1] - t.mean[i]:.1f} mN/m between "
                                        f"{t.conc[i - 1]:g} and {t.conc[i]:g} mM. A real isotherm declines gradually; "
                                        "check these points (a step makes the slope-based results unreliable)."))
            break
    r.studio_unreliable = unreliable   # carried with the result; excluded from beta^M and beta^sigma
    if r.gamma0_mN_m > gamma_solvent + 1.0:
        flags.append(Flag(ds.sheet, f"The lowest-concentration surface tension ({r.gamma0_mN_m:.1f} mN/m) is above "
                                    f"the solvent value on Info ({gamma_solvent:g} mN/m); check calibration."))
    big_sd = [c for c, s in zip(t.conc, t.sd) if s is not None and s > 1.0]
    if big_sd:
        flags.append(Flag(ds.sheet, f"{len(big_sd)} concentration(s) have run-to-run SD above 1 mN/m "
                                    f"(first at {big_sd[0]:g} mM); check those runs.", "note"))
    return r


def _conductivity(ds: Dataset, kind: str | None, flags: list[Flag]) -> object | None:
    if not ds.conductivity:
        return None
    c, k = ds.conductivity
    if kind in ("nonionic",):
        flags.append(Flag(ds.sheet, "Conductivity of a nonionic surfactant has no micellization break; "
                                    "conductivity data not analysed.", "note"))
        return None
    if len(c) < MIN_COND_POINTS:
        flags.append(Flag(ds.sheet, f"Only {len(c)} conductivity points; at least {MIN_COND_POINTS} are needed."))
        return None
    try:
        return ca.cmc_from_conductivity_curve(c, k)
    except ValueError as e:
        flags.append(Flag(ds.sheet, f"Conductivity: no CMC found ({e})."))
        return None


def _c_at_gamma(t, gamma_ref: float) -> tuple[float | None, str | None]:
    """Concentration where the fitted pre-CMC line reaches gamma_ref, and why not if it cannot."""
    if t is None:
        return None, "no surface tension analysis"
    s = t.premicellar_slope_mN_per_m_per_log10C
    if s >= 0:
        return None, "cannot be read: the pre-CMC slope is not negative"
    if gamma_ref < t.gamma_at_cmc_mN_per_m:
        return None, (f"cannot be read: this curve never reaches it (surface tension at the CMC is "
                      f"{t.gamma_at_cmc_mN_per_m:.1f} mN/m); lower the surface pressure on Info if every curve "
                      "needs a common value")
    lc = math.log10(t.cmc_mM) + (gamma_ref - t.gamma_at_cmc_mN_per_m) / s
    c = 10 ** lc
    if c < t.premicellar_x_min_mM * 0.999:
        return c, "extrapolated below the fitted pre-CMC range"
    return c, None


def global_beta_least_squares(alphas, cmcs, cmc1, cmc2, lo=-30.0, hi=10.0):
    """Single beta minimising sum (1/CMC_exp - 1/CMC_Rubingh(beta))^2: the criterion researchers apply
    with Excel Solver, evaluated with the toolkit's own Rubingh predictor. Grid then golden section."""
    def ssd(b):
        tot = 0.0
        for a, c in zip(alphas, cmcs):
            p = rubingh_predict_cmc_mix(a, b, cmc1, cmc2)
            if p is None or p <= 0:
                return math.inf
            tot += (1.0 / c - 1.0 / p) ** 2
        return tot
    grid = [lo + i * (hi - lo) / 800 for i in range(801)]
    vals = [ssd(b) for b in grid]
    i = min(range(len(grid)), key=vals.__getitem__)
    a, b = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
    g = (math.sqrt(5) - 1) / 2
    x1, x2 = b - g * (b - a), a + g * (b - a)
    f1, f2 = ssd(x1), ssd(x2)
    for _ in range(80):
        if f1 < f2:
            b, x2, f2 = x2, x1, f1
            x1 = b - g * (b - a); f1 = ssd(x1)
        else:
            a, x1, f1 = x1, x2, f2
            x2 = a + g * (b - a); f2 = ssd(x2)
    best = (a + b) / 2
    return best, ssd(best), (i in (0, len(grid) - 1))


def analyse(study: Study) -> Results:
    info = study.info
    T = float(info["temperature_C"]) + 273.15
    gsolv = float(info["gamma_solvent"])
    gamma_ref = gsolv - float(info["pi_ref"])
    flags = [Flag("Reading", n, "note") for n in study.notes]
    calls = ["curve_analysis.cmc_from_surface_tension_curve", "curve_analysis.plateau_is_statistically_suspect"]
    curves: dict[str, Curve] = {}
    kinds = (info["s1_type"], info["s2_type"])

    # ---------------------------------------------------------------- pure surfactants
    pure = []
    for idx, ds in enumerate(study.pure):
        kind = kinds[idx]
        cv = Curve(ds.sheet, None, _tension(ds, flags, gsolv), _conductivity(ds, kind, flags))
        curves[ds.sheet] = cv
        row = {"sheet": ds.sheet, "name": info[f"s{idx + 1}_name"], "type": kind}
        t, k = cv.t, cv.k
        if t:
            st = _system_type(kind, float(info["salt_mM"]))
            gmax = ads.gibbs_gamma_max(t.premicellar_slope_mN_per_m_per_lnC, st, T)
            pi_cmc = gsolv - t.gamma_at_cmc_mN_per_m
            row.update(cmc_t=t.cmc_mM, gamma_cmc=t.gamma_at_cmc_mN_per_m, pi_cmc=pi_cmc, c20=t.c20_mM,
                       pc20=t.pC20, cmc_c20=(t.cmc_mM / t.c20_mM if t.c20_mM else None),
                       n_gibbs=2 if st == "ionic_no_added_salt" else 1, gamma_max=gmax,
                       a_min=ads.gibbs_a_min(gmax) if gmax > 0 else None)
            if kind == "zwitterionic":
                flags.append(Flag(ds.sheet, "Zwitterionic surfactant treated with Gibbs n = 1.", "note"))
            if st == "ionic_excess_electrolyte" and float(info["salt_mM"]) < 10 * t.cmc_mM:
                flags.append(Flag(ds.sheet, f"Added salt ({info['salt_mM']:g} mM) is less than 10 x CMC: n = 1 assumes "
                                            "excess electrolyte; Gamma_max and A_min may be off by up to 2x."))
        if k:
            row.update(cmc_k=k.cmc_mM, s1=k.slope_below_cmc, s2=k.slope_above_cmc,
                       alpha_ion=k.slope_above_cmc / k.slope_below_cmc, beta_cb=k.counterion_binding_degree)
            calls.append("curve_analysis.cmc_from_conductivity_curve")
        if t:
            factor = None
            if kind == "ionic":
                if k:
                    factor = 1.0 + k.counterion_binding_degree
                else:
                    flags.append(Flag(ds.sheet, "Free energy of micellization not computed: an ionic surfactant needs "
                                                "the counterion binding from conductivity.", "note"))
            else:
                factor = 1.0
            if factor is not None:
                dg = td.gibbs_free_energy_micellization(td.cmc_to_mole_fraction(t.cmc_mM / 1000.0), T, factor)
                row["dg_mic"] = dg
                if row.get("gamma_max"):
                    row["dg_ads"] = dg - (row["pi_cmc"] * 1e-3 / row["gamma_max"]) / 1000.0
                calls.append("thermodynamics.gibbs_free_energy_micellization")
        if t and k and abs(t.cmc_mM / k.cmc_mM - 1) > 0.25:
            flags.append(Flag(ds.sheet, f"CMC from surface tension ({t.cmc_mM:.3g} mM) and conductivity "
                                        f"({k.cmc_mM:.3g} mM) differ by more than 25%."))
        pure.append(row)
    calls += ["adsorption.gibbs_gamma_max", "adsorption.gibbs_a_min"]

    # ------------------------------------------------------------- mixtures, per sheet
    mix_rows = []
    for ds in study.mixes:
        cv = Curve(ds.sheet, ds.alpha1, _tension(ds, flags, gsolv), _conductivity(ds, "ionic", flags))
        curves[ds.sheet] = cv
        row = {"sheet": ds.sheet, "alpha1": ds.alpha1}
        if cv.t:
            row.update(cmc_t=cv.t.cmc_mM, gamma_cmc=cv.t.gamma_at_cmc_mN_per_m, pc20=cv.t.pC20, c20=cv.t.c20_mM,
                       unreliable=cv.t.studio_unreliable)
        if cv.k:
            row.update(cmc_k=cv.k.cmc_mM, beta_cb=cv.k.counterion_binding_degree)
        mix_rows.append(row)
    mix_rows.sort(key=lambda r: r["alpha1"])

    # ------------------------------------------------- mixed micelle: Rubingh beta^M
    rub = {}
    ok = [curves[s].t is not None and not curves[s].t.studio_unreliable for s in L_PURE]
    cmc1 = pure[0].get("cmc_t") if ok[0] else None
    cmc2 = pure[1].get("cmc_t") if ok[1] else None
    skipped = [r["sheet"] for r in mix_rows if r.get("cmc_t") and r.get("unreliable")]
    if skipped:
        flags.append(Flag("Rubingh", "Left out of beta^M and beta^sigma because their isotherm is flagged: "
                                     + ", ".join(skipped) + "."))
    pts = [(r["alpha1"], r["cmc_t"]) for r in mix_rows if r.get("cmc_t") and not r.get("unreliable")]
    if cmc1 and cmc2 and len(pts) >= 2:
        a_s, c_s = [p[0] for p in pts], [p[1] for p in pts]
        rub["cmc1"], rub["cmc2"] = cmc1, cmc2
        try:
            reg = mm.rubingh_beta_regression(a_s, c_s, cmc1, cmc2)
            rub.update(beta_mean=reg.beta_mean, beta_std=reg.beta_std, n_used=reg.n_points_used,
                       n_skipped=reg.n_points_skipped)
            per = dict(zip(reg.alpha1_used, zip(reg.x1_values, reg.betas)))
            if reg.n_points_skipped:
                flags.append(Flag("Rubingh", f"{reg.n_points_skipped} composition(s) have no Rubingh solution "
                                             "(near-ideal, or the mixed CMC is inconsistent with the pure CMCs)."))
        except ValueError as e:
            per = {}
            flags.append(Flag("Rubingh", f"Rubingh beta not computed: {e}"))
        gb, gssd, at_edge = global_beta_least_squares(a_s, c_s, cmc1, cmc2)
        rub.update(beta_global=gb, ssd_global=gssd)
        if at_edge:
            flags.append(Flag("Rubingh", "The least-squares beta sits at the edge of the search range (-30 to 10); "
                                         "the data do not fix beta."))
        for r in mix_rows:
            a = r["alpha1"]
            r["cmc_ideal"] = mm.clint_ideal_cmc(a, cmc1, cmc2)
            p = rubingh_predict_cmc_mix(a, gb, cmc1, cmc2)
            r["cmc_pred_global"] = p
            if a in per:
                x1, b = per[a]
                f1, f2 = mm.activity_coefficients(x1, b)
                r.update(x1=x1, beta_m=b, f1=f1, f2=f2, g_ex=mm.excess_free_energy(x1, f1, f2, T))
        calls += ["mixed_micelle.rubingh_beta_regression", "mixed_micelle.clint_ideal_cmc",
                  "mixed_micelle.activity_coefficients", "mixed_micelle.excess_free_energy",
                  "mixture_model_selection.rubingh_predict_cmc_mix"]
        if len(pts) >= 3:
            try:
                sel = select_mixture_model(a_s, c_s, cmc1, cmc2)
                rub["model"] = sel.selected_model
                rub["bic"] = {k.name: k.bic for k in sel.candidates}
                calls.append("mixture_model_selection.select_mixture_model")
            except ValueError as e:
                flags.append(Flag("Rubingh", f"Model comparison not run: {e}", "note"))
        if len(pts) < 5:
            flags.append(Flag("Rubingh", f"Only {len(pts)} mixed compositions; 5 or more are recommended.", "note"))
    else:
        flags.append(Flag("Rubingh", "beta^M needs the CMC of both pure surfactants and of at least two mixtures."))

    # --------------------------------------------- mixed monolayer: Rosen beta^sigma
    ros = {"gamma_ref": gamma_ref}
    for i, ds in enumerate(study.pure):
        if not ok[i]:
            continue
        c, why = _c_at_gamma(curves[ds.sheet].t, gamma_ref)
        curves[ds.sheet].c_ref = c
        ros[f"c{i + 1}"] = c
        if why:
            flags.append(Flag(ds.sheet, f"Rosen: concentration at {gamma_ref:.1f} mN/m {why}.",
                              "note" if c is not None else "warning"))
    bsig = []
    if ros.get("c1") and ros.get("c2"):
        for r in mix_rows:
            if r.get("unreliable"):
                continue
            c, why = _c_at_gamma(curves[r["sheet"]].t, gamma_ref)
            curves[r["sheet"]].c_ref = c
            r["c_ref"] = c
            if why:
                flags.append(Flag(r["sheet"], f"Rosen: concentration at {gamma_ref:.1f} mN/m {why}.",
                                  "note" if c is not None else "warning"))
            if c is None:
                continue
            x = mm.solve_rosen_monolayer_x(r["alpha1"], c, ros["c1"], ros["c2"])
            if x is None:
                flags.append(Flag(r["sheet"], "Rosen: no monolayer composition solves at this alpha1."))
                continue
            b = mm.rosen_beta_sigma(x, r["alpha1"], c, ros["c1"])
            r.update(x1_sigma=x, beta_sigma=b); bsig.append(b)
        calls += ["mixed_micelle.solve_rosen_monolayer_x", "mixed_micelle.rosen_beta_sigma"]
    if bsig:
        ros["beta_mean"] = sum(bsig) / len(bsig)
        ros["beta_std"] = math.sqrt(sum((b - ros["beta_mean"]) ** 2 for b in bsig) / len(bsig))

    # ------------------------------------------------------- Rosen synergism tests
    syn = []
    bm = rub.get("beta_mean")
    if bm is not None:
        lr = abs(math.log(cmc1 / cmc2))
        syn.append({"test": "Mixed micelle formation (CMC)", "criterion": "beta^M < 0 and |beta^M| > |ln(CMC1/CMC2)|",
                    "lhs": abs(bm), "rhs": lr, "result": bm < 0 and abs(bm) > lr})
    bs = ros.get("beta_mean")
    if bs is not None:
        lr = abs(math.log(ros["c1"] / ros["c2"]))
        syn.append({"test": "Surface tension reduction efficiency",
                    "criterion": "beta^sigma < 0 and |beta^sigma| > |ln(C1/C2)| at the reference tension",
                    "lhs": abs(bs), "rhs": lr, "result": bs < 0 and abs(bs) > lr})
    if bm is not None and bs is not None:
        d = bs - bm
        lr = abs(math.log((ros["c1"] * cmc2) / (ros["c2"] * cmc1)))
        syn.append({"test": "Surface tension reduction effectiveness",
                    "criterion": "beta^sigma - beta^M < 0 and |beta^sigma - beta^M| > |ln(C1 CMC2 / (C2 CMC1))|",
                    "lhs": abs(d), "rhs": lr, "result": d < 0 and abs(d) > lr})

    # ------------------------------------------------------ temperature series
    temps = []
    for i in (0, 1):
        pts_t = [(tc + 273.15, row[1 + i]) for row in study.temperature for tc in [row[0]] if row[1 + i]]
        if not pts_t:
            continue
        name = info[f"s{i + 1}_name"]
        if len(pts_t) < 3:
            flags.append(Flag(L_TEMP, f"{name}: {len(pts_t)} temperature(s); 3 or more are needed."))
            continue
        kind = kinds[i]
        factor = 1.0 if kind != "ionic" else (1.0 + pure[i]["beta_cb"] if pure[i].get("beta_cb") else None)
        if factor is None:
            flags.append(Flag(L_TEMP, f"{name}: enthalpy not computed; an ionic surfactant needs counterion binding "
                                      "from conductivity (Surfactant sheet)."))
            continue
        res = td.vant_hoff_multi_point_fit([td.cmc_to_mole_fraction(c / 1000.0) for _, c in pts_t],
                                           [tk for tk, _ in pts_t], factor)
        temps.append({"name": name, "T": [tk for tk, _ in pts_t], "cmc": [c for _, c in pts_t],
                      "dH": res.delta_H_kJ_per_mol, "dS": res.delta_S_J_per_mol_K, "dCp": res.delta_Cp_J_per_mol_K,
                      "T_ref": res.reference_temperature_K, "r2": res.r_squared, "dG": res.delta_G_fitted_kJ_per_mol})
        calls.append("thermodynamics.vant_hoff_multi_point_fit")

    return Results(info, T, gamma_ref, curves, pure, mix_rows, rub, ros, syn, temps, flags, sorted(set(calls)))


L_TEMP = "Temperature series"
L_PURE = ("Surfactant 1", "Surfactant 2")
