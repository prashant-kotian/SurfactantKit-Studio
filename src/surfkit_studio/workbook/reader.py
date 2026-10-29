"""Read a filled template back into plain data. Only the researcher's input cells are read; the
log, mean and SD columns are recomputed here, never trusted from the file."""
from __future__ import annotations

import io
import math
import statistics
from dataclasses import dataclass, field

import openpyxl

from . import layout as L


class WorkbookError(ValueError):
    """The file cannot be analysed (wrong layout, unreadable cells)."""


@dataclass
class Tension:
    conc: list[float]
    runs: list[list[float]]          # the runs actually filled, per concentration
    mean: list[float]
    sd: list[float | None]           # None where fewer than two runs were filled


@dataclass
class Dataset:
    sheet: str
    alpha1: float | None             # None for a pure surfactant
    tension: Tension | None
    conductivity: tuple[list[float], list[float]] | None   # (conc mM, kappa in the Info unit)


@dataclass
class Study:
    info: dict
    pure: list[Dataset]
    mixes: list[Dataset]
    temperature: list[tuple[float, float | None, float | None]]
    notes: list[str] = field(default_factory=list)   # non-blocking reading notes


def _num(v_formula, v_value, where: str):
    """A numeric input cell: number, empty (None), or an error naming the cell."""
    v = v_value if v_value is not None else v_formula
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        raise WorkbookError(f"{where}: expected a number, found {v!r}.")
    if isinstance(v, (int, float)):
        if not math.isfinite(v):
            raise WorkbookError(f"{where}: not a finite number.")
        return float(v)
    if isinstance(v, str) and v.startswith("="):
        raise WorkbookError(f"{where} holds a formula with no saved value. Open the file in Excel, save it, "
                            "and upload it again (or type the number itself).")
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        raise WorkbookError(f"{where}: expected a number, found {v!r}.") from None


def _read_data_sheet(wf, wv, name: str, is_mix: bool, notes: list[str]) -> Dataset:
    sf, sv = wf[name], wv[name]
    alpha = None
    if is_mix:
        alpha = _num(sf[L.ALPHA_CELL].value, sv[L.ALPHA_CELL].value, f"{name}!{L.ALPHA_CELL}")
        if alpha is None or not 0 < alpha < 1:
            raise WorkbookError(f"{name}!{L.ALPHA_CELL}: alpha1 must be a mole fraction strictly between 0 and 1.")
    conc, runs, means, sds = [], [], [], []
    k_conc, k_val = [], []
    for r in range(L.FIRST_ROW, L.LAST_ROW + 1):
        def cell(col):
            return _num(sf.cell(r, col).value, sv.cell(r, col).value,
                        f"{name}!{openpyxl.utils.get_column_letter(col)}{r}")
        c = cell(L.T_COLS["conc"])
        reps = [x for x in (cell(L.T_COLS["run1"]), cell(L.T_COLS["run2"]), cell(L.T_COLS["run3"])) if x is not None]
        if c is None and reps:
            raise WorkbookError(f"{name} row {r}: surface tension given without a concentration.")
        if c is not None:
            if c <= 0:
                raise WorkbookError(f"{name}!A{r}: concentration must be positive (log scale).")
            if not reps:
                notes.append(f"{name} row {r}: concentration {c:g} mM has no surface tension; row skipped.")
            else:
                if any(not 10 <= g <= 80 for g in reps):
                    raise WorkbookError(f"{name} row {r}: surface tension outside 10-80 mN/m; check the unit.")
                conc.append(c); runs.append(reps); means.append(statistics.fmean(reps))
                sds.append(statistics.stdev(reps) if len(reps) > 1 else None)
        kc, kv = cell(L.K_COLS["conc"]), cell(L.K_COLS["kappa"])
        if (kc is None) != (kv is None):
            raise WorkbookError(f"{name} row {r}: conductivity needs both a concentration and a reading.")
        if kc is not None:
            k_conc.append(kc); k_val.append(kv)
    order = sorted(range(len(conc)), key=lambda i: conc[i])
    tension = None
    if conc:
        if len(set(conc)) != len(conc):
            raise WorkbookError(f"{name}: the same concentration appears twice in the surface tension table; "
                                "put repeat measurements in the run 2 and run 3 columns of one row.")
        tension = Tension([conc[i] for i in order], [runs[i] for i in order],
                          [means[i] for i in order], [sds[i] for i in order])
        single = sum(1 for x in runs if len(x) == 1)
        if single:
            notes.append(f"{name}: {single} concentration(s) have a single run, so no SD there.")
    ko = sorted(range(len(k_conc)), key=lambda i: k_conc[i])
    cond = ([k_conc[i] for i in ko], [k_val[i] for i in ko]) if k_conc else None
    return Dataset(name, alpha, tension, cond)


def read_workbook(data: bytes) -> Study:
    try:
        wf = openpyxl.load_workbook(io.BytesIO(data), data_only=False)
        wv = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    except Exception as e:  # noqa: BLE001 - any unreadable file is the same answer for the user
        raise WorkbookError(f"Not a readable .xlsx file ({type(e).__name__}).") from None
    missing = [s for s in (L.INFO, *L.PURE) if s not in wf.sheetnames]
    if missing:
        raise WorkbookError("This is not the Studio template: missing sheet(s) " + ", ".join(missing)
                            + ". Download the template and fill that in.")
    info = {}
    for key, (row, label, default, allowed) in L.INFO_FIELDS.items():
        v = wv[L.INFO].cell(row, L.INFO_VALUE_COL).value
        if v is None or (isinstance(v, str) and not v.strip()):
            v = default
        if isinstance(default, (int, float)) and not isinstance(default, bool):
            v = _num(v, v, f"Info!B{row} ({label})")
        else:
            v = str(v).strip()
            if allowed and v not in allowed:
                raise WorkbookError(f"Info!B{row} ({label}): must be one of {', '.join(allowed)}.")
        info[key] = v
    info["sig_figs"] = int(info["sig_figs"]) if info["sig_figs"] else 2
    if not 1 <= info["sig_figs"] <= 6:
        raise WorkbookError("Info: significant figures shown must be between 1 and 6.")
    notes: list[str] = []
    pure = [_read_data_sheet(wf, wv, s, False, notes) for s in L.PURE]
    mix_names = sorted((s for s in wf.sheetnames if s.startswith(L.MIX_PREFIX)),
                       key=lambda s: (len(s), s))
    mixes = [_read_data_sheet(wf, wv, s, True, notes) for s in mix_names]
    mixes = [m for m in mixes if m.tension or m.conductivity]
    alphas = [m.alpha1 for m in mixes]
    if len(set(alphas)) != len(alphas):
        raise WorkbookError("Two Mix sheets have the same alpha1.")
    temp = []
    if L.TEMPERATURE in wf.sheetnames:
        sf, sv = wf[L.TEMPERATURE], wv[L.TEMPERATURE]
        for r in range(L.TEMP_FIRST_ROW, L.TEMP_FIRST_ROW + L.TEMP_N_ROWS):
            vals = [_num(sf.cell(r, c).value, sv.cell(r, c).value, f"{L.TEMPERATURE}!R{r}C{c}") for c in (1, 2, 3)]
            if vals[0] is not None and (vals[1] is not None or vals[2] is not None):
                temp.append(tuple(vals))
    return Study(info, pure, mixes, temp, notes)
