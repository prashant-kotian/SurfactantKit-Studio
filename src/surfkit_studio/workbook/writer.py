"""The completed workbook: the researcher's data back in the template layout, the toolkit's
results, Excel Solver sheets laid out the way researchers already work (live formulas, Solver
model preloaded), a comparison of manual and toolkit values, flags and the plots.

Values are stored at full precision; the number format shows the significant figures chosen on
the Info sheet. Solver sheets keep working precision, since convergence has to be visible there.
"""
from __future__ import annotations

import io
import math

from openpyxl.comments import Comment
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName

from . import layout as L
from .analysis import Results
from .reader import Study
from .template import CALC_FILL, INPUT_FILL, new_workbook

BOLD = Font(bold=True)
TITLE = Font(bold=True, size=12)
HEAD_FILL = PatternFill("solid", fgColor="DCE6F1")
SOLVER_FILL = PatternFill("solid", fgColor="E2EFDA")     # cells Solver changes

S_PER = "Rubingh per-point (Solver)"
S_GLOB = "Rubingh global (Solver)"
S_ROSEN = "Rosen per-point (Solver)"


def sig_format(v, n: int) -> str:
    if not isinstance(v, (int, float)) or isinstance(v, bool) or v == 0 or not math.isfinite(v):
        return "General"
    e = math.floor(math.log10(abs(v)))
    if e < -3 or e >= 6:
        return ("0." + "0" * (n - 1) if n > 1 else "0") + "E+00"
    d = max(0, n - 1 - e)
    return "0" if d == 0 else "0." + "0" * d


def _put(ws, r, c, v, n=None, comment=None, bold=False, fill=None):
    cell = ws.cell(r, c, v)
    if n is not None:
        cell.number_format = sig_format(v, n)
    if comment:
        cell.comment = Comment(comment, "SurfactantKit Studio", width=320, height=120)
    if bold:
        cell.font = BOLD
    if fill:
        cell.fill = fill
    return cell


def _header(ws, r, labels, c0=1):
    for j, h in enumerate(labels):
        cell = ws.cell(r, c0 + j, h); cell.font = BOLD; cell.fill = HEAD_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="top")


def _widths(ws, w: dict):
    for c, x in w.items():
        ws.column_dimensions[get_column_letter(c)].width = x


def preload_solver(ws, objective: str, changing: str, constraints: list[tuple[str, int, float | str]]):
    """Store a Solver model on the sheet the way Excel does (hidden sheet-scoped names), so the
    researcher opens Data > Solver and presses Solve. rel: 1 <=, 2 =, 3 >=."""
    q = f"'{ws.title}'!"
    changing = ",".join(q + part for part in changing.split(","))   # every part of a union qualified
    names = {"solver_opt": q + objective, "solver_adj": changing, "solver_typ": "2", "solver_val": "0",
             "solver_ver": "3", "solver_eng": "1", "solver_neg": "2", "solver_num": str(len(constraints)),
             "solver_cvg": "0.0001", "solver_drv": "2", "solver_est": "1", "solver_itr": "2147483647",
             "solver_mip": "2147483647", "solver_mni": "30", "solver_mrt": "0.075", "solver_msl": "2",
             "solver_nod": "2147483647", "solver_nwt": "1", "solver_pre": "0.000001", "solver_rbv": "2",
             "solver_rlx": "2", "solver_rsd": "0", "solver_scl": "1", "solver_sho": "2", "solver_ssz": "100",
             "solver_tim": "2147483647", "solver_tol": "0.01"}
    for i, (lhs, rel, rhs) in enumerate(constraints, 1):
        names[f"solver_lhs{i}"] = q + lhs
        names[f"solver_rel{i}"] = str(rel)
        names[f"solver_rhs{i}"] = str(rhs)
    for k, v in names.items():
        ws.defined_names[k] = DefinedName(k, attr_text=v, hidden=True)


# ------------------------------------------------------------------ data sheets
def _write_data(wb, study: Study, n: int):
    """The researcher's inputs go back exactly as typed; the calculated columns (log, mean, SD) are
    displayed to n significant figures."""
    for ds in list(study.pure) + list(study.mixes):
        ws = wb[ds.sheet]
        if ds.tension:
            t = ds.tension
            for i, (c, runs) in enumerate(zip(t.conc, t.runs)):
                r = L.FIRST_ROW + i
                ws.cell(r, L.T_COLS["conc"], c)
                for j, g in enumerate(runs):
                    ws.cell(r, L.T_COLS["run1"] + j, g)
                ws.cell(r, L.T_COLS["log"]).number_format = "0.00"
                ws.cell(r, L.T_COLS["mean"]).number_format = sig_format(t.mean[i], n)
                if t.sd[i] is not None:
                    ws.cell(r, L.T_COLS["sd"]).number_format = sig_format(t.sd[i], n)
        if ds.conductivity:
            for i, (c, k) in enumerate(zip(*ds.conductivity)):
                ws.cell(L.FIRST_ROW + i, L.K_COLS["conc"], c)
                ws.cell(L.FIRST_ROW + i, L.K_COLS["kappa"], k)
    ws = wb[L.TEMPERATURE]
    for i, row in enumerate(study.temperature):
        for j, v in enumerate(row):
            if v is not None:
                ws.cell(L.TEMP_FIRST_ROW + i, 1 + j, v)


# --------------------------------------------------------------- results sheets
PURE_ROWS = [
    ("CMC (surface tension)", "cmc_t", "mM", "Break point of surface tension vs log10 C (two or three straight "
     "segments, lowest total residual): curve_analysis.cmc_from_surface_tension_curve."),
    ("Surface tension at CMC, gamma_CMC", "gamma_cmc", "mN/m", "From the fitted segments at the CMC."),
    ("Surface pressure at CMC, pi_CMC", "pi_cmc", "mN/m", "pi_CMC = gamma_solvent - gamma_CMC (solvent value on Info)."),
    ("C20", "c20", "mM", "Concentration that lowers the surface tension by 20 mN/m."),
    ("pC20 (efficiency)", "pc20", "", "pC20 = -log10(C20 / M)."),
    ("CMC / C20", "cmc_c20", "", "Ratio of CMC to C20."),
    ("Gibbs prefactor n", "n_gibbs", "", "n = 2 for an ionic surfactant without added salt, 1 otherwise."),
    ("Gamma_max", "gamma_max_u", "umol/m^2", "Gamma_max = -(1/nRT) d gamma / d ln C from the pre-CMC slope "
     "(adsorption.gibbs_gamma_max). A straight line through a curved isotherm gives the average slope of the "
     "declining region, so Gamma_max is a lower estimate when the decline is curved."),
    ("A_min", "a_min", "nm^2", "A_min = 1 / (N_A Gamma_max) (adsorption.gibbs_a_min)."),
    ("CMC (conductivity)", "cmc_k", "mM", "Intersection of two straight lines of conductivity vs C "
     "(curve_analysis.cmc_from_conductivity_curve)."),
    ("Slope below CMC, S1", "s1", "unit/mM", "Conductivity slope below the CMC."),
    ("Slope above CMC, S2", "s2", "unit/mM", "Conductivity slope above the CMC."),
    ("Degree of ionization, alpha", "alpha_ion", "", "alpha = S2 / S1."),
    ("Counterion binding, beta", "beta_cb", "", "beta = 1 - S2 / S1."),
    ("Free energy of micellization", "dg_mic", "kJ/mol", "Ionic: (1 + beta) RT ln X_CMC; nonionic: RT ln X_CMC; "
     "X_CMC = CMC / (CMC + 55.5 M); CMC from surface tension (thermodynamics.gibbs_free_energy_micellization)."),
    ("Free energy of adsorption", "dg_ads", "kJ/mol", "dG_ads = dG_mic - pi_CMC / Gamma_max (Rosen)."),
]


def _results_pure(wb, res: Results, n):
    ws = wb.create_sheet("Results - pure")
    ws["A1"] = "Pure surfactants (SurfactantKit)"; ws["A1"].font = TITLE
    ws["A2"] = f"Temperature {res.temperature_K:.2f} K. Hover over a value for its method and formula."
    _header(ws, 4, ["Quantity", res.pure[0]["name"], res.pure[1]["name"], "Unit"])
    for p in res.pure:
        if p.get("gamma_max"):
            p["gamma_max_u"] = p["gamma_max"] * 1e6
    for i, (label, key, unit, method) in enumerate(PURE_ROWS):
        r = 5 + i
        ws.cell(r, 1, label)
        for j, p in enumerate(res.pure):
            v = p.get(key)
            if key == "n_gibbs":
                _put(ws, r, 2 + j, v, None, method)
            else:
                _put(ws, r, 2 + j, v if v is not None else "not computed", n if v is not None else None, method)
        ws.cell(r, 4, unit.replace("unit", res.info["kappa_unit"]))
    _widths(ws, {1: 38, 2: 18, 3: 18, 4: 14})
    return ws


MIX_COLS = [
    ("Sheet", "sheet", None, None),
    ("alpha1", "alpha1", None, "Mole fraction of surfactant 1 in the total surfactant (from the Mix sheet)."),
    ("CMC, surface tension (mM)", "cmc_t", "n", "Break point of surface tension vs log10 C."),
    ("CMC, conductivity (mM)", "cmc_k", "n", "Two-line intersection of conductivity vs C."),
    ("gamma_CMC (mN/m)", "gamma_cmc", "n", None),
    ("pC20", "pc20", "n", None),
    ("CMC ideal, Clint (mM)", "cmc_ideal", "n", "1/CMC_ideal = alpha1/CMC1 + (1 - alpha1)/CMC2."),
    ("X1 (micelle)", "x1", "n", "Solved from X1^2 ln(alpha1 CMC/(X1 CMC1)) = (1-X1)^2 ln((1-alpha1) CMC/((1-X1) CMC2)) "
     "(mixed_micelle.solve_rubingh_x)."),
    ("beta^M", "beta_m", "n", "beta^M = ln(alpha1 CMC/(X1 CMC1)) / (1-X1)^2 (Rubingh)."),
    ("f1", "f1", "n", "f1 = exp(beta^M (1-X1)^2)."),
    ("f2", "f2", "n", "f2 = exp(beta^M X1^2)."),
    ("G_ex (kJ/mol)", "g_ex", "n", "G_ex = RT (X1 ln f1 + (1-X1) ln f2)."),
    ("CMC, Rubingh at global beta (mM)", "cmc_pred_global", "n", "Rubingh prediction with the least-squares beta "
     "(mixture_model_selection.rubingh_predict_cmc_mix)."),
    ("C at reference gamma (mM)", "c_ref", "n", "Where the fitted pre-CMC line reaches the reference surface tension."),
    ("X1^sigma (monolayer)", "x1_sigma", "n", "Rosen: same equation as Rubingh with the concentrations at the reference "
     "surface tension (mixed_micelle.solve_rosen_monolayer_x)."),
    ("beta^sigma", "beta_sigma", "n", "beta^sigma = ln(alpha1 C12/(X1 C1)) / (1-X1)^2 (mixed_micelle.rosen_beta_sigma)."),
]


def _results_mix(wb, res: Results, n):
    ws = wb.create_sheet("Results - mixtures")
    ws["A1"] = "Mixtures: mixed micelle (Rubingh) and mixed monolayer (Rosen)"; ws["A1"].font = TITLE
    _header(ws, 3, [c[0] for c in MIX_COLS])
    for i, row in enumerate(res.mix_rows):
        for j, (_, key, fmt, method) in enumerate(MIX_COLS):
            v = row.get(key)
            _put(ws, 4 + i, 1 + j, v if v is not None else "", n if fmt and v is not None else None, method)
    r = 6 + len(res.mix_rows)
    rub, ros = res.rubingh, res.rosen
    ws.cell(r, 1, "Mixed micelle (Rubingh)").font = TITLE
    lines = [("CMC1 used (mM)", rub.get("cmc1"), "Surfactant 1, from surface tension."),
             ("CMC2 used (mM)", rub.get("cmc2"), "Surfactant 2, from surface tension."),
             ("beta^M, mean of compositions", rub.get("beta_mean"), "Arithmetic mean of the per-composition beta^M "
              "(mixed_micelle.rubingh_beta_regression), the usual published practice."),
             ("beta^M, standard deviation", rub.get("beta_std"), "A large spread means one beta does not describe "
              "every composition."),
             ("beta^M, global least squares", rub.get("beta_global"), "One beta minimising sum (1/CMC_exp - "
              "1/CMC_Rubingh)^2 over all compositions: the criterion researchers apply with Excel Solver."),
             ("Sum of (1/CMC_exp - 1/CMC_Rubingh)^2 at that beta", rub.get("ssd_global"), "In (1/mM)^2."),
             ("Best mixing model (BIC)", rub.get("model"), "Clint (ideal), Rubingh (one beta) or EOMMM (two "
              "parameters), lowest BIC (mixture_model_selection.select_mixture_model).")]
    for k, (lab, v, m) in enumerate(lines):
        ws.cell(r + 1 + k, 1, lab)
        _put(ws, r + 1 + k, 2, v if v is not None else "not computed", n if isinstance(v, float) else None, m)
    r += len(lines) + 2
    ws.cell(r, 1, "Mixed monolayer (Rosen)").font = TITLE
    lines = [("Reference surface tension (mN/m)", ros.get("gamma_ref"), "gamma_solvent - pi_ref (both on Info)."),
             ("C1 at reference tension (mM)", ros.get("c1"), None), ("C2 at reference tension (mM)", ros.get("c2"), None),
             ("beta^sigma, mean of compositions", ros.get("beta_mean"), None),
             ("beta^sigma, standard deviation", ros.get("beta_std"), None)]
    for k, (lab, v, m) in enumerate(lines):
        ws.cell(r + 1 + k, 1, lab)
        _put(ws, r + 1 + k, 2, v if v is not None else "not computed", n if isinstance(v, float) else None, m)
    r += len(lines) + 2
    ws.cell(r, 1, "Synergism (Rosen's criteria)").font = TITLE
    _header(ws, r + 1, ["Test", "Synergism?", "|left side|", "right side", "Criterion"])
    for k, s in enumerate(res.synergism):
        rr = r + 2 + k
        ws.cell(rr, 1, s["test"]); ws.cell(rr, 2, "Yes" if s["result"] else "No").font = BOLD
        _put(ws, rr, 3, s["lhs"], n); _put(ws, rr, 4, s["rhs"], n)
        ws.cell(rr, 5, s["criterion"])
    if not res.synergism:
        ws.cell(r + 2, 1, "Not evaluated: needs beta^M and/or beta^sigma.")
    _widths(ws, {1: 40, 2: 16, **{c: 14 for c in range(3, len(MIX_COLS) + 1)}})
    ws.column_dimensions["B"].width = 18
    return ws


def _results_temperature(wb, res: Results, n):
    if not res.temperature:
        return
    ws = wb.create_sheet("Results - temperature")
    ws["A1"] = "Thermodynamics from the temperature series (multi-point Gibbs-Helmholtz fit)"; ws["A1"].font = TITLE
    _header(ws, 3, ["Surfactant", "dH_mic (kJ/mol)", "dS_mic (J/mol K)", "dCp (J/mol K)", "Reference T (K)", "R^2"])
    for i, t in enumerate(res.temperature):
        ws.cell(4 + i, 1, t["name"])
        for j, key in enumerate(("dH", "dS", "dCp", "T_ref", "r2")):
            _put(ws, 4 + i, 2 + j, t[key], n if key != "T_ref" else 5,
                 "thermodynamics.vant_hoff_multi_point_fit" if j == 0 else None)
    _widths(ws, {1: 22, 2: 16, 3: 16, 4: 16, 5: 16, 6: 10})


# ---------------------------------------------------------------- Solver sheets
def _solver_per_point(wb, title, sheet, res: Results, inputs, rows, sym, n=2):
    """Per-composition Rubingh-type solve: Solver sets sum((F1 - F2)^2) to zero by changing X1."""
    ws = wb.create_sheet(sheet)
    ws["A1"] = title; ws["A1"].font = TITLE
    ws["A2"] = ("Data > Solver > Solve (the model is already set: minimise the sum of square diff by changing the "
                "green X cells). Start values are 0.5; the inputs are the toolkit's values and you may overwrite them.")
    for k, (lab, v) in enumerate(inputs):
        ws.cell(4 + k, 1, lab).font = BOLD
        _put(ws, 4 + k, 2, v, n, fill=INPUT_FILL)
    c_a, c_b = "$B$" + str(4 + len(inputs) - 2), "$B$" + str(4 + len(inputs) - 1)   # the two pure-component cells
    h = 4 + len(inputs) + 1
    _header(ws, h, ["alpha1", f"{sym[0]} (mM)", f"{sym[1]} (Solver changes)", "F1", "F2", "Solver cell (F1 - F2)",
                    "Square diff", sym[2], "f1", "f2"])
    first = h + 1
    for i, (a, cm) in enumerate(rows):
        r = first + i
        ws.cell(r, 1, a); _put(ws, r, 2, cm, n)
        x = ws.cell(r, 3, 0.5); x.fill = SOLVER_FILL; x.number_format = "0.0000"
        f = {4: f"=C{r}^2*LN(A{r}*B{r}/(C{r}*{c_a}))", 5: f"=(1-C{r})^2*LN((1-A{r})*B{r}/((1-C{r})*{c_b}))",
             6: f"=D{r}-E{r}", 7: f"=F{r}^2", 8: f"=LN(A{r}*B{r}/(C{r}*{c_a}))/(1-C{r})^2",
             9: f"=EXP(H{r}*(1-C{r})^2)", 10: f"=EXP(H{r}*C{r}^2)"}
        for c, form in f.items():
            cell = ws.cell(r, c, form); cell.fill = CALC_FILL
            cell.number_format = "0.00E+00" if c in (6, 7) else "0.000"
    last = first + len(rows) - 1
    s = last + 2
    ws.cell(s, 6, "Sum of square diff").font = BOLD
    ws.cell(s, 7, f"=SUM(G{first}:G{last})").number_format = "0.00E+00"
    ws.cell(s + 1, 6, f"Mean {sym[2]}").font = BOLD
    ws.cell(s + 1, 8, f"=AVERAGE(H{first}:H{last})").number_format = "0.000"
    preload_solver(ws, f"$G${s}", f"$C${first}:$C${last}",
                   [(f"$C${first}:$C${last}", 3, 0.0001), (f"$C${first}:$C${last}", 1, 0.9999)])
    _widths(ws, {1: 30, 2: 16, 3: 16, 4: 12, 5: 12, 6: 16, 7: 14, 8: 12, 9: 10, 10: 10})
    return ws, first, last, s


def _solver_global(wb, res: Results, n=2):
    """Ogino-Abe layout: for a beta, Solver finds X1 so the predicted bulk composition matches alpha1;
    beta is chosen by the CMC residual (1/CMC exptl - 1/CMC correl)^2."""
    rub = res.rubingh
    rows = [(r["alpha1"], r["cmc_t"]) for r in res.mix_rows if r.get("cmc_t")]
    ws = wb.create_sheet(S_GLOB)
    ws["A1"] = "Rubingh, one beta for all compositions (Excel Solver; layout of Ogino and Abe, Mixed Surfactant Systems)"
    ws["A1"].font = TITLE
    ws["A2"] = ("One run: Data > Solver > Solve (preset: minimise the CMC residual sum by changing beta and the X1 "
                "cells, with every Solver cell = 0). Or the usual way: type a beta, solve the X1 cells for the "
                "composition sum, write beta and the CMC residual sum in the table on the right, repeat.")
    for k, (lab, v, fill) in enumerate([("CMC1 (mM)", rub.get("cmc1"), INPUT_FILL), ("CMC2 (mM)", rub.get("cmc2"), INPUT_FILL),
                                        ("beta (Solver changes)", -1.0, SOLVER_FILL)]):
        ws.cell(4 + k, 1, lab).font = BOLD
        _put(ws, 4 + k, 2, v, n if fill is INPUT_FILL else None, fill=fill)
    heads = ["alpha1", "CMC mix (mM)", "X1 (Solver changes)", "f1", "f2", "C1", "C2", "C1+C2", "alpha1 predicted",
             "Solver cell", "Square diff", "CMC ideal", "1/CMC exptl", "1/CMC ideal", "1/CMC correl", "CMC residual"]
    _header(ws, 8, heads)
    first = 9
    for i, (a, cm) in enumerate(rows):
        r = first + i
        ws.cell(r, 1, a); _put(ws, r, 2, cm, n)
        x = ws.cell(r, 3, 0.5); x.fill = SOLVER_FILL; x.number_format = "0.0000"
        f = {4: f"=EXP($B$6*(1-C{r})^2)", 5: f"=EXP($B$6*C{r}^2)", 6: f"=C{r}*D{r}*$B$4", 7: f"=(1-C{r})*E{r}*$B$5",
             8: f"=F{r}+G{r}", 9: f"=F{r}/H{r}", 10: f"=A{r}-I{r}", 11: f"=J{r}^2",
             12: f"=1/(A{r}/$B$4+(1-A{r})/$B$5)", 13: f"=1/B{r}", 14: f"=1/L{r}", 15: f"=1/H{r}",
             16: f"=(M{r}-O{r})^2"}
        for c, form in f.items():
            cell = ws.cell(r, c, form); cell.fill = CALC_FILL
            cell.number_format = "0.00E+00" if c in (10, 11, 16) else "0.0000"
    last = first + len(rows) - 1
    s = last + 2
    ws.cell(s, 10, "Sum of sq diff (composition)").font = BOLD
    ws.cell(s, 11, f"=SUM(K{first}:K{last})").number_format = "0.00E+00"
    ws.cell(s + 1, 10, "Sum of CMC residual (choose beta by this)").font = BOLD
    ws.cell(s + 1, 16, f"=SUM(P{first}:P{last})").number_format = "0.00E+00"
    _header(ws, 8, ["beta tried", "Sum of CMC residual"], c0=18)
    for k in range(10):
        ws.cell(9 + k, 18).fill = INPUT_FILL; ws.cell(9 + k, 19).fill = INPUT_FILL
    preload_solver(ws, f"$P${s + 1}", f"$B$6,$C${first}:$C${last}",
                   [(f"$J${first}:$J${last}", 2, 0),
                    (f"$C${first}:$C${last}", 3, 0.0001), (f"$C${first}:$C${last}", 1, 0.9999)])
    _widths(ws, {1: 22, 2: 14, 3: 16, **{c: 12 for c in range(4, 17)}, 18: 12, 19: 18})
    return ws, first, last, s


def _comparison(wb, res: Results, per, glob, rosen, n):
    ws = wb.create_sheet("Comparison")
    ws["A1"] = "Manual (Excel Solver) against toolkit"; ws["A1"].font = TITLE
    ws["A2"] = ("Live: run Solver on the three Solver sheets and this sheet updates. The toolkit values use the CMCs "
                "on Results; if you change a CMC in a Solver sheet, the difference includes that change.")
    _header(ws, 4, ["Quantity", "alpha1", "Manual (Excel Solver)", "Toolkit", "Manual - toolkit", "Status"])
    r = 5
    tol = "1E-8"

    def row(label, a, manual_ref, toolkit, solved_ref):
        nonlocal r
        ws.cell(r, 1, label); ws.cell(r, 2, a)
        ws.cell(r, 3, f"={manual_ref}").number_format = "0.000"
        _put(ws, r, 4, toolkit, None)
        ws.cell(r, 4).number_format = "0.000"
        ws.cell(r, 5, f'=IF({solved_ref}>{tol},"",C{r}-D{r})').number_format = "0.0000"
        ws.cell(r, 6, f'=IF({solved_ref}>{tol},"manual not solved yet","solved")')
        r += 1

    if per:
        sh, first, last, s = per[0].title, *per[1:]
        rows = [m for m in res.mix_rows if m.get("cmc_t")]
        for i, m in enumerate(rows):
            if m.get("beta_m") is not None:
                row("beta^M (per composition)", m["alpha1"], f"'{sh}'!H{first + i}", m["beta_m"], f"'{sh}'!G{first + i}")
        for i, m in enumerate(rows):
            if m.get("x1") is not None:
                row("X1 (micelle)", m["alpha1"], f"'{sh}'!C{first + i}", m["x1"], f"'{sh}'!G{first + i}")
        if res.rubingh.get("beta_mean") is not None:
            row("beta^M, mean", "all", f"'{sh}'!H{s + 1}", res.rubingh["beta_mean"], f"'{sh}'!G{s}")
    if glob and res.rubingh.get("beta_global") is not None:
        sh, first, last, s = glob[0].title, *glob[1:]
        row("beta^M, global (CMC residual)", "all", f"'{sh}'!B6", res.rubingh["beta_global"], f"'{sh}'!K{s}")
        ws.cell(r - 1, 7, "Solved means the composition sum is ~0; beta itself is optimal only if the CMC residual "
                          "sum was minimised (one-run Solver preset, or the beta table).")
    if rosen:
        sh, first, last, s = rosen[0].title, *rosen[1:]
        rows = [m for m in res.mix_rows if m.get("c_ref") is not None]
        for i, m in enumerate(rows):
            if m.get("beta_sigma") is not None:
                row("beta^sigma (per composition)", m["alpha1"], f"'{sh}'!H{first + i}", m["beta_sigma"],
                    f"'{sh}'!G{first + i}")
        if res.rosen.get("beta_mean") is not None:
            row("beta^sigma, mean", "all", f"'{sh}'!H{s + 1}", res.rosen["beta_mean"], f"'{sh}'!G{s}")
    _widths(ws, {1: 32, 2: 8, 3: 22, 4: 12, 5: 16, 6: 22, 7: 60})


def _flags(wb, res: Results):
    ws = wb.create_sheet("Flags")
    ws["A1"] = "Data and method flags"; ws["A1"].font = TITLE
    _header(ws, 3, ["Where", "Level", "Message"])
    if not res.flags:
        ws.cell(4, 1, "No flags.")
    for i, f in enumerate(res.flags):
        ws.cell(4 + i, 1, f.where); ws.cell(4 + i, 2, f.level)
        c = ws.cell(4 + i, 3, f.message); c.alignment = Alignment(wrap_text=True, vertical="top")
    _widths(ws, {1: 20, 2: 10, 3: 110})


def _plots(wb, pngs: list[tuple[str, bytes]]):
    ws = wb.create_sheet("Plots")
    ws["A1"] = "Plots (also in the ZIP as PNG and xmgrace .agr)"; ws["A1"].font = TITLE
    for i, (name, png) in enumerate(pngs):
        img = XLImage(io.BytesIO(png))
        img.width, img.height = img.width * 0.35, img.height * 0.35
        row = 3 + (i // 2) * 24
        col = "A" if i % 2 == 0 else "K"
        ws.add_image(img, f"{col}{row}")


def _methods(wb, res: Results):
    ws = wb.create_sheet("Methods")
    ws["A1"] = "How the results were computed"; ws["A1"].font = TITLE
    lines = ["Every result comes from SurfactantKit (open source, MIT licence). Functions called:"] + \
            [f"  {c}" for c in res.calls] + [
        "",
        "Surface tension: the mean of the filled runs at each concentration is analysed; SD is shown as error bars.",
        "Rosen beta-sigma: concentrations where each fitted pre-CMC line reaches the reference surface tension.",
        f"Results are displayed to {res.info['sig_figs']} significant figures (Info); cells hold full precision.",
    ]
    for i, t in enumerate(lines):
        ws.cell(3 + i, 1, t)
    ws.column_dimensions["A"].width = 120


def write_output(study: Study, res: Results, pngs: list[tuple[str, bytes]]) -> bytes:
    n = res.info["sig_figs"]
    info = {k: v for k, v in res.info.items()}
    wb = new_workbook(info, [(m.sheet, m.alpha1) for m in study.mixes])
    _write_data(wb, study, n)
    _results_pure(wb, res, n)
    _results_mix(wb, res, n)
    _results_temperature(wb, res, n)
    rub = res.rubingh
    rows = [(m["alpha1"], m["cmc_t"]) for m in res.mix_rows if m.get("cmc_t")]
    per = glob = rosen = None
    if rub.get("cmc1") and rows:
        per = _solver_per_point(wb, "Rubingh, beta^M at each composition (Excel Solver)", S_PER, res,
                                [("CMC1 (mM)", rub["cmc1"]), ("CMC2 (mM)", rub["cmc2"])], rows,
                                ("CMC mix", "X1", "beta^M"), n)
        glob = _solver_global(wb, res, n)
    ros = res.rosen
    rrows = [(m["alpha1"], m["c_ref"]) for m in res.mix_rows if m.get("c_ref") is not None]
    if ros.get("c1") and ros.get("c2") and rrows:
        rosen = _solver_per_point(wb, "Rosen, beta^sigma at each composition (Excel Solver)", S_ROSEN, res,
                                  [("Reference surface tension (mN/m)", ros["gamma_ref"]),
                                   ("C1 at reference (mM)", ros["c1"]), ("C2 at reference (mM)", ros["c2"])], rrows,
                                  ("C mix at reference", "X1^sigma", "beta^sigma"), n)
    _comparison(wb, res, per, glob, rosen, n)
    _flags(wb, res)
    _plots(wb, pngs)
    _methods(wb, res)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
