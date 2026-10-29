"""Synthetic but physically consistent binary-mixture data with KNOWN parameters, written into the
Studio template. The analysis must recover the parameters it was built from.

Pure surfactants follow the Szyszkowski isotherm up to their CMC (flat above). Mixtures follow
Rubingh (CMC_mix from beta_M) and Rosen (at every surface tension, the mixed concentration is the
Rubingh prediction from the two pure monomer concentrations with beta_sigma).
"""
from __future__ import annotations

import io
import math
import random

from surfactantkit.mixture_model_selection import rubingh_predict_cmc_mix

from surfkit_studio.workbook import layout as L
from surfkit_studio.workbook.template import new_workbook

R, T = 8.314462618, 298.15
GAMMA0 = 72.0
# (CMC mM, Gamma_max mol/m^2, Szyszkowski K 1/mM, Gibbs n)
S1 = (8.0, 3.0e-6, 1.1, 2)
S2 = (0.05, 2.5e-6, 376.0, 2)
BETA_M, BETA_SIGMA = -6.0, -8.0
ALPHAS = (0.1, 0.3, 0.5, 0.7, 0.9)


def gamma_pure(c, p):
    cmc, gm, k, n = p
    c = min(c, cmc)
    return GAMMA0 - n * R * T * gm * 1000.0 * math.log(1.0 + k * c)


def c_pure_at(gamma, p):
    """Monomer concentration of a pure surfactant at surface tension gamma (Szyszkowski inverse)."""
    cmc, gm, k, n = p
    return (math.exp((GAMMA0 - gamma) / (n * R * T * gm * 1000.0)) - 1.0) / k


def mixed_curve(alpha):
    """(conc, gamma) pairs of the mixed isotherm below its CMC, and the CMC itself."""
    cmc_mix = rubingh_predict_cmc_mix(alpha, BETA_M, S1[0], S2[0])
    pts = []
    g = GAMMA0 - 0.3
    while g > 20:
        c = rubingh_predict_cmc_mix(alpha, BETA_SIGMA, c_pure_at(g, S1), c_pure_at(g, S2))
        if c is None or c >= cmc_mix:
            break
        pts.append((c, g)); g -= 0.1
    return pts, cmc_mix


def gamma_mixed(c, curve, cmc_mix):
    pts = curve
    if c >= pts[-1][0]:
        return pts[-1][1]
    if c <= pts[0][0]:
        return GAMMA0
    for (c0, g0), (c1, g1) in zip(pts, pts[1:]):
        if c0 <= c <= c1:
            w = (math.log(c) - math.log(c0)) / (math.log(c1) - math.log(c0))
            return g0 + w * (g1 - g0)
    return pts[-1][1]


def _grid(cmc, n=18, lo=0.02, hi=6.0):
    return [cmc * lo * (hi / lo) ** (i / (n - 1)) for i in range(n)]


def _fill(ws, concs, gammas, rng, noise, kappa=None):
    for i, (c, g) in enumerate(zip(concs, gammas)):
        r = L.FIRST_ROW + i
        ws.cell(r, L.T_COLS["conc"], round(c, 6))
        for key in ("run1", "run2", "run3"):
            ws.cell(r, L.T_COLS[key], round(g + rng.gauss(0, noise), 2))
    if kappa:
        for i, (c, k) in enumerate(kappa):
            ws.cell(L.FIRST_ROW + i, L.K_COLS["conc"], round(c, 6))
            ws.cell(L.FIRST_ROW + i, L.K_COLS["kappa"], round(k, 4))


def conductivity(cmc, s1=80.0, s2=30.0, n=16):
    """uS/cm vs mM: two straight lines meeting at the CMC; counterion binding = 1 - s2/s1."""
    cs = [cmc * (0.2 + 1.8 * i / (n - 1)) for i in range(n)]
    return [(c, s1 * c if c <= cmc else s1 * cmc + s2 * (c - cmc)) for c in cs]


def build(noise=0.05, seed=1, with_conductivity=True) -> bytes:
    rng = random.Random(seed)
    wb = new_workbook({"s1_name": "Synthetic A", "s2_name": "Synthetic B", "temperature_C": T - 273.15,
                       "gamma_solvent": GAMMA0})
    for name, p in zip(L.PURE, (S1, S2)):
        cs = _grid(p[0])
        _fill(wb[name], cs, [gamma_pure(c, p) for c in cs], rng, noise,
              conductivity(p[0]) if with_conductivity else None)
    for name, a in zip(L.mix_sheet_names(), ALPHAS):
        curve, cmc_mix = mixed_curve(a)
        cs = _grid(cmc_mix)
        _fill(wb[name], cs, [gamma_mixed(c, curve, cmc_mix) for c in cs], rng, noise)
        wb[name][L.ALPHA_CELL] = a
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


def truth():
    """Exact values the analysis should recover."""
    out = {"cmc1": S1[0], "cmc2": S2[0], "beta_m": BETA_M, "beta_sigma": BETA_SIGMA,
           "gamma_max1": S1[1], "gamma_max2": S2[1],
           "cmc_mix": {a: rubingh_predict_cmc_mix(a, BETA_M, S1[0], S2[0]) for a in ALPHAS}}
    return out
