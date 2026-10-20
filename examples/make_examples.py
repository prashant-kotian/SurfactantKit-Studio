"""Regenerate the example datasets.

SDS_surface_tension.csv : REAL measured data, open dataset doi:10.5281/zenodo.17232763
                          (same values SurfactantKit's own tests use).
synthetic_*.csv         : SYNTHETIC, generated below from stated parameters so the app
                          can be tried and round-trip tested. Not measurements.
"""
import csv
import math
import random
from pathlib import Path

HERE = Path(__file__).parent
R = 8.314462618

SDS_C = [0.40577109375, 0.8115421875, 1.623084375, 3.24616875, 6.4923375, 12.984675, 25.96935, 51.9387]
SDS_G = [69.85933451975876, 67.9370105943862, 62.892649575815454, 54.57301518905874,
         42.87619733622359, 37.91402789831731, 37.44295519808575, 36.79102755846683]
# copied verbatim from Surfactant-Toolkit tests/test_curve_analysis.py (_SDS_CONCS/_SDS_TENSIONS);
# tests/test_examples.py re-checks them against that file when it is available


def write(name, header, rows):
    with open(HERE / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    write("SDS_surface_tension.csv", ["Concentration (mM)", "Surface tension (mN/m)"], zip(SDS_C, SDS_G))

    # conductivity: CMC 8.2 mM, S1 = 72 uS/cm per mM, alpha = 0.30 (beta = 0.70), 1% noise
    rnd = random.Random(7)
    cmc, s1, s2 = 8.2, 72.0, 72.0 * 0.30
    rows = []
    for c in [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 14, 16, 18, 20]:
        k = 2.0 + (s1 * c if c <= cmc else s1 * cmc + s2 * (c - cmc))
        rows.append((c, round(k * (1 + rnd.gauss(0, 0.004)), 2)))
    write("synthetic_conductivity.csv", ["Concentration (mM)", "Conductivity (uS/cm)"], rows)

    # CMC vs T from dH(298.15) = -1.0 kJ/mol, dCp = -500 J/(mol K), beta = 0.70, CMC(298.15) = 8.2 mM
    T0, f, dH0, dCp = 298.15, 1.70, -1000.0, -500.0
    dG0 = f * R * T0 * math.log(8.2e-3 / 55.5)
    dS0 = (dH0 - dG0) / T0
    rows = []
    for T in [288.15, 293.15, 298.15, 303.15, 308.15, 313.15, 318.15, 323.15]:
        dG = dH0 + dCp * (T - T0) - T * (dS0 + dCp * math.log(T / T0))
        x = math.exp(dG / (f * R * T))
        rows.append((round(T - 273.15, 2), round(x * 55.5 * 1000, 4)))
    write("synthetic_cmc_vs_T.csv", ["Temperature (C)", "CMC (mM)"], rows)

    # binary mixture: Rubingh regular solution, beta = -3.0, CMC1 = 14.8 mM, CMC2 = 8.0 mM, 0.5% noise
    cmc1, cmc2, beta = 14.8, 8.0, -3.0
    rows = []
    for a in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        def mix_cmc(x):
            f1, f2 = math.exp(beta * (1 - x) ** 2), math.exp(beta * x ** 2)
            return 1.0 / (a / (f1 * cmc1) + (1 - a) / (f2 * cmc2)), f1

        def h(x):                     # micellar x1 must equal alpha1 * cmc_mix / (f1 * cmc1)
            c, f1 = mix_cmc(x)
            return x - a * c / (f1 * cmc1)
        lo, hi = 1e-9, 1 - 1e-9
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if h(lo) * h(mid) > 0 else (lo, mid)
        rows.append((a, round(mix_cmc((lo + hi) / 2)[0] * (1 + rnd.gauss(0, 0.005)), 4)))
    write("synthetic_mixed_cmc.csv", ["alpha1 (mole fraction)", "CMC mix (mM)"], rows)

    # fluorescence quenching: N = 60, Ct = 20 mM, CMC = 8 mM, I0 = 1000, 0.5% noise (Turro-Yekta)
    rows = [(q, round(1000 * math.exp(-60 * q / 12.0) * (1 + rnd.gauss(0, 0.005)), 2))
            for q in [0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15]]
    write("synthetic_quenching.csv", ["Quencher (mM)", "Intensity (a.u.)"], rows)

    # SLS Debye plot: N = 60, monomer 288.38 g/mol (SDS), A2 = 4e-4 cm^3 mol/g^2,
    # dn/dc = 0.12 mL/g, 632.8 nm, n = 1.333
    Mw, A2 = 60 * 288.38, 4e-4
    lam = 632.8e-7
    K = 4 * math.pi ** 2 * 1.333 ** 2 * 0.12 ** 2 / (6.02214076e23 * lam ** 4)
    rows = [(c, float(f"{K * c / (1 / Mw + 2 * A2 * c) * (1 + rnd.gauss(0, 0.003)):.5e}"))
            for c in [0.002, 0.004, 0.006, 0.008, 0.010, 0.012]]
    write("synthetic_sls.csv", ["C - CMC (g/mL)", "Rayleigh ratio (1/cm)"], rows)

    # solubilization: naphthalene-like solute, S_w = 0.217 mM, CMC = 8.2 mM, MSR = 0.05, 1% noise
    sw, cmc, msr = 0.217, 8.2, 0.05
    rows = [(c, round((sw if c <= cmc else sw + msr * (c - cmc)) * (1 + rnd.gauss(0, 0.01)), 4))
            for c in [2, 5, 10, 15, 20, 30, 40, 60]]
    write("synthetic_solubilization.csv", ["Surfactant (mM)", "Solubilized solute (mM)"], rows)

    # HLD salinity scan (ionic form, 25 C): k = 0.16, Cc = 0.5, i.e. ln S* = 0.16 EACN - 0.5, 1% noise
    rows = [(e, round(math.exp(0.16 * e - 0.5) * (1 + rnd.gauss(0, 0.01)), 3)) for e in [6, 8, 10, 12, 14]]
    write("synthetic_salinity_scan.csv", ["EACN", "Optimal salinity S* (g/100 mL)"], rows)


if __name__ == "__main__":
    main()
