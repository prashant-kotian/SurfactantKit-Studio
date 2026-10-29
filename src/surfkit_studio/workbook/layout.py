"""Cell layout shared by the template, the reader and the output writer, so the three cannot drift
apart. Concentrations are always mM; surface tension mN/m."""
from __future__ import annotations

INFO = "Info"
PURE = ("Surfactant 1", "Surfactant 2")
MIX_PREFIX = "Mix "
DEFAULT_ALPHAS = (0.1, 0.3, 0.5, 0.7, 0.9)
TEMPERATURE = "Temperature series"

# Info sheet: key -> (row, label, default, allowed values or None)
INFO_FIELDS = {
    "s1_name": (3, "Surfactant 1 name", "Surfactant 1", None),
    "s1_type": (4, "Surfactant 1 type", "ionic", ("ionic", "nonionic", "zwitterionic")),
    "s2_name": (5, "Surfactant 2 name", "Surfactant 2", None),
    "s2_type": (6, "Surfactant 2 type", "ionic", ("ionic", "nonionic", "zwitterionic")),
    "temperature_C": (7, "Temperature (C)", 25.0, None),
    "salt_name": (8, "Added salt (name, or none)", "none", None),
    "salt_mM": (9, "Added salt concentration (mM, 0 if none)", 0.0, None),
    "gamma_solvent": (10, "Surface tension of the solvent (mN/m)", 72.0, None),
    "pi_ref": (11, "Surface pressure for Rosen beta-sigma (mN/m)", 20.0, None),
    "kappa_unit": (12, "Conductivity unit", "uS/cm", ("uS/cm", "mS/cm")),
    "sig_figs": (13, "Significant figures shown in results", 2, None),
}
INFO_VALUE_COL = 2

# data sheets (pure and mixtures)
HEADER_ROW = 4
FIRST_ROW = 5
N_ROWS = 60
LAST_ROW = FIRST_ROW + N_ROWS - 1
ALPHA_CELL = "B2"          # mixtures only
T_COLS = {"conc": 1, "log": 2, "run1": 3, "run2": 4, "run3": 5, "mean": 6, "sd": 7}
K_COLS = {"conc": 9, "kappa": 10}
T_HEADERS = ["C (mM)", "log10 C", "Surface tension run 1 (mN/m)", "Run 2 (mN/m)", "Run 3 (mN/m)",
             "Mean (mN/m)", "SD (mN/m)"]
K_HEADERS = ["C (mM)", "Conductivity (unit on Info)"]

# temperature series: columns T, CMC1, CMC2
TEMP_FIRST_ROW = 5
TEMP_N_ROWS = 20


def mix_sheet_names(n: int = len(DEFAULT_ALPHAS)) -> list[str]:
    return [f"{MIX_PREFIX}{i + 1}" for i in range(n)]
