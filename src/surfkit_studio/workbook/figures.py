"""Every plot of a workbook analysis, described once (FigSpec) and rendered twice: PNG through
matplotlib and an xmgrace .agr project, so the two cannot disagree. Labels are keyboard-only."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .. import plotting as P
from .analysis import Results


@dataclass
class Series:
    label: str
    x: list[float]
    y: list[float]
    dy: list[float] | None = None     # error bars (SD of the runs)
    kind: str = "points"              # "points" or "line"
    dashed: bool = False


@dataclass
class FigSpec:
    name: str                          # file stem
    title: str
    xlabel: str
    ylabel: str
    xlog: bool = False
    series: list[Series] = field(default_factory=list)
    ylog: bool = False


def _tension_fig(name, title, tension, t, gamma_ref=None) -> FigSpec:
    f = FigSpec(name, title, "Concentration (mM)", "Surface tension (mN/m)", xlog=True)
    f.series.append(Series("Mean of runs", tension.conc, tension.mean,
                           [s or 0.0 for s in tension.sd] if any(s for s in tension.sd) else None))
    if t is not None:
        lc = math.log10(t.cmc_mM)
        x0 = t.premicellar_x_min_mM
        f.series.append(Series("Pre-CMC fit", [x0, t.cmc_mM],
                               [t.gamma_at_cmc_mN_per_m + t.premicellar_slope_mN_per_m_per_log10C * (math.log10(x) - lc)
                                for x in (x0, t.cmc_mM)], kind="line"))
        hi = max(tension.conc)
        f.series.append(Series("Post-CMC fit", [t.cmc_mM, hi],
                               [t.postmicellar_intercept_mN_per_m + t.postmicellar_slope_mN_per_m_per_log10C * math.log10(x)
                                for x in (t.cmc_mM, hi)], kind="line", dashed=True))
        ys = tension.mean
        f.series.append(Series(f"CMC = {t.cmc_mM:.3g} mM", [t.cmc_mM, t.cmc_mM], [min(ys) - 1, max(ys) + 1],
                               kind="line", dashed=True))
    return f


def _cond_fig(name, title, cond, k, unit) -> FigSpec:
    c, kap = cond
    f = FigSpec(name, title, "Concentration (mM)", f"Conductivity ({unit})")
    f.series.append(Series("Measured", c, kap))
    if k is not None:
        # each segment: the toolkit's slope with its least-squares intercept on that segment's own points
        for lab, s, pts, dashed in (
                ("Below CMC", k.slope_below_cmc, [(x, y) for x, y in zip(c, kap) if x <= k.cmc_mM], False),
                ("Above CMC", k.slope_above_cmc, [(x, y) for x, y in zip(c, kap) if x > k.cmc_mM], True)):
            if pts:
                b = sum(y - s * x for x, y in pts) / len(pts)
                x0, x1 = (min(c), k.cmc_mM) if not dashed else (k.cmc_mM, max(c))
                f.series.append(Series(lab, [x0, x1], [b + s * x0, b + s * x1], kind="line", dashed=dashed))
    return f


def build_figs(study, res: Results) -> list[FigSpec]:
    figs = []
    unit = res.info["kappa_unit"]
    for ds in list(study.pure) + list(study.mixes):
        cv = res.curves[ds.sheet]
        label = (res.info["s1_name"] if ds.sheet == "Surfactant 1" else res.info["s2_name"]
                 if ds.sheet == "Surfactant 2" else f"alpha1 = {ds.alpha1:g}")
        stem = ds.sheet.replace(" ", "_").lower()
        if ds.tension:
            figs.append(_tension_fig(f"{stem}_tension", f"{label}: surface tension", ds.tension, cv.t))
        if ds.conductivity:
            figs.append(_cond_fig(f"{stem}_conductivity", f"{label}: conductivity", ds.conductivity, cv.k, unit))
    # all isotherms together, with the Rosen reference line
    iso = FigSpec("all_isotherms", "All isotherms", "Concentration (mM)", "Surface tension (mN/m)", xlog=True)
    xs = []
    for ds in list(study.pure) + list(study.mixes):
        if ds.tension:
            lab = res.info["s1_name"] if ds.sheet == "Surfactant 1" else (
                res.info["s2_name"] if ds.sheet == "Surfactant 2" else f"alpha1 = {ds.alpha1:g}")
            iso.series.append(Series(lab, ds.tension.conc, ds.tension.mean))
            xs += ds.tension.conc
    if xs:
        iso.series.append(Series(f"Rosen reference, {res.gamma_ref:.1f} mN/m", [min(xs), max(xs)],
                                 [res.gamma_ref, res.gamma_ref], kind="line", dashed=True))
        figs.append(iso)
    rub = res.rubingh
    rows = [r for r in res.mix_rows if r.get("cmc_t")]
    if rub.get("cmc1") and rows:
        f = FigSpec("cmc_mix_vs_alpha", "Mixed CMC against composition", "alpha1", "CMC of mixture (mM)",
                    ylog=max(rub["cmc1"], rub["cmc2"]) / min(rub["cmc1"], rub["cmc2"]) > 20)
        a = [0.0] + [r["alpha1"] for r in rows] + [1.0]
        f.series.append(Series("Measured", a, [rub["cmc2"]] + [r["cmc_t"] for r in rows] + [rub["cmc1"]]))
        grid = [i / 100 for i in range(1, 100)]
        from surfactantkit import mixed_micelle as mm
        from surfactantkit.mixture_model_selection import rubingh_predict_cmc_mix
        f.series.append(Series("Ideal (Clint)", grid, [mm.clint_ideal_cmc(x, rub["cmc1"], rub["cmc2"]) for x in grid],
                               kind="line", dashed=True))
        if rub.get("beta_global") is not None:
            pts = [(x, rubingh_predict_cmc_mix(x, rub["beta_global"], rub["cmc1"], rub["cmc2"])) for x in grid]
            pts = [(x, y) for x, y in pts if y]
            f.series.append(Series(f"Rubingh, beta = {rub['beta_global']:.2f}", [p[0] for p in pts],
                                   [p[1] for p in pts], kind="line"))
        figs.append(f)
    bm = [(r["alpha1"], r["beta_m"]) for r in res.mix_rows if r.get("beta_m") is not None]
    bs = [(r["alpha1"], r["beta_sigma"]) for r in res.mix_rows if r.get("beta_sigma") is not None]
    if bm or bs:
        f = FigSpec("beta_vs_alpha", "Interaction parameters against composition", "alpha1", "beta")
        if bm:
            f.series.append(Series("beta^M (micelle)", [p[0] for p in bm], [p[1] for p in bm]))
        if bs:
            f.series.append(Series("beta^sigma (monolayer)", [p[0] for p in bs], [p[1] for p in bs]))
        figs.append(f)
    for tr in res.temperature:
        f = FigSpec(f"cmc_vs_T_{tr['name']}".replace(" ", "_"), f"{tr['name']}: CMC against temperature",
                    "Temperature (K)", "CMC (mM)")
        f.series.append(Series("Measured", tr["T"], tr["cmc"]))
        figs.append(f)
    return figs


# ------------------------------------------------------------------- renderers
_COLORS = [P.DATA, P.FIT, P.ALT, P.MARK, P.MUTED, "#E69F00", "#56B4E9", "#000000"]


def render_png(f: FigSpec) -> bytes:
    fig, ax = P.new(13.0, 8.5)
    for i, s in enumerate(f.series):
        col = _COLORS[i % len(_COLORS)]
        if s.kind == "points":
            if s.dy:
                ax.errorbar(s.x, s.y, yerr=s.dy, fmt="o", ms=3.5, color=col, capsize=2, lw=0.8, label=s.label, zorder=3)
            else:
                ax.scatter(s.x, s.y, s=16, color=col, label=s.label, zorder=3)
        else:
            ax.plot(s.x, s.y, color=col, lw=1.3, ls="--" if s.dashed else "-", label=s.label)
    if f.xlog:
        ax.set_xscale("log")
    if f.ylog:
        ax.set_yscale("log")
    ax.set_xlabel(f.xlabel); ax.set_ylabel(f.ylabel); ax.set_title(f.title, fontsize=9)
    ax.legend(fontsize=6, loc="best")
    return P.to_png(fig)


def _nice_step(span: float, target: int = 6) -> float:
    """A 1, 2 or 5 x 10^k tick spacing giving about `target` major ticks over `span`."""
    raw = span / target
    k = 10 ** math.floor(math.log10(raw))
    return next(m * k for m in (1, 2, 5, 10) if m * k >= raw)


def _agr_str(s: str) -> str:
    return s.replace('"', "'")


def render_agr(f: FigSpec) -> str:
    """A Grace 5.1 project: one graph, one set per series (xydy where error bars exist)."""
    xs = [x for s in f.series for x in s.x]
    ys = [y for s in f.series for y in s.y]
    ys += [y + d for s in f.series if s.dy for y, d in zip(s.y, s.dy)]
    ys += [y - d for s in f.series if s.dy for y, d in zip(s.y, s.dy)]
    def lin(lo, hi, frac):
        pad = (hi - lo) * frac or 1.0
        return lo - pad, hi + pad

    def logr(vals):
        v = [x for x in vals if x > 0]
        return 10 ** math.floor(math.log10(min(v))), 10 ** math.ceil(math.log10(max(v)))
    xmin, xmax = logr(xs) if f.xlog else lin(min(xs), max(xs), 0.05)
    ymin, ymax = logr(ys) if f.ylog else lin(min(ys), max(ys), 0.08)
    out = ["# Grace project file", "#", "@version 50125", "@page size 792, 612", "@g0 on", "@with g0",
           f"@    world {xmin:.6g}, {ymin:.6g}, {xmax:.6g}, {ymax:.6g}",
           "@    view 0.150000, 0.150000, 1.150000, 0.850000",
           f'@    title "{_agr_str(f.title)}"', "@    title size 1.000000",
           f'@    xaxis  label "{_agr_str(f.xlabel)}"', f'@    yaxis  label "{_agr_str(f.ylabel)}"',
           "@    legend on", "@    legend 0.85, 0.82", "@    legend char size 0.700000"]
    for ax, is_log, lo, hi in (("x", f.xlog, xmin, xmax), ("y", f.ylog, ymin, ymax)):
        if is_log:
            out += [f"@    {ax}axes scale Logarithmic", f"@    {ax}axis  tick major 10",
                    f"@    {ax}axis  tick minor ticks 9"]
        else:
            out += [f"@    {ax}axes scale Normal", f"@    {ax}axis  tick major {_nice_step(hi - lo):.6g}",
                    f"@    {ax}axis  tick minor ticks 1"]
    for i, s in enumerate(f.series):
        col = 1 + (i % 14)
        out += [f"@    s{i} hidden false", f"@    s{i} type {'xydy' if s.dy else 'xy'}"]
        if s.kind == "points":
            out += [f"@    s{i} symbol {1 + i % 10}", f"@    s{i} symbol size 0.600000", f"@    s{i} symbol color {col}",
                    f"@    s{i} symbol fill pattern 1", f"@    s{i} symbol fill color {col}", f"@    s{i} line type 0"]
        else:
            out += [f"@    s{i} symbol 0", f"@    s{i} line type 1", f"@    s{i} line linestyle {3 if s.dashed else 1}",
                    f"@    s{i} line linewidth 1.5", f"@    s{i} line color {col}"]
        if s.dy:
            out += [f"@    s{i} errorbar on", f"@    s{i} errorbar color {col}"]
        out.append(f'@    s{i} legend  "{_agr_str(s.label)}"')
    for i, s in enumerate(f.series):
        out += [f"@target G0.S{i}", f"@type {'xydy' if s.dy else 'xy'}"]
        for j, (x, y) in enumerate(zip(s.x, s.y)):
            out.append(f"{x:.8g} {y:.8g}" + (f" {s.dy[j]:.8g}" if s.dy else ""))
        out.append("&")
    return "\n".join(out) + "\n"
