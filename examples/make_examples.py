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


if __name__ == "__main__":
    main()
