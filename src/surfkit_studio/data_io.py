"""Read a researcher's CSV/XLSX, propose a column mapping, convert units.

Unit conversion happens once, here, into each column's canonical unit (the
first entry in Column.units). Nothing downstream ever sees a non-canonical
unit. The mapping is always shown to the researcher for confirmation; the
auto-detection is only a suggestion.
"""
from __future__ import annotations

import io
import re

import pandas as pd

from .catalog.base import DatasetSpec

# factor to the canonical unit of each family
TO_CANONICAL = {
    "mM": 1.0, "M": 1000.0, "uM": 0.001,
    "mN/m": 1.0, "dyn/cm": 1.0,
    "uS/cm": 1.0, "mS/cm": 1000.0, "S/m": 10000.0,
}


def read_table(name: str, raw: bytes) -> pd.DataFrame:
    if name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(raw))
    else:
        text = raw.decode("utf-8-sig", errors="replace")
        header = text.splitlines()[0] if text else ""
        # decide from the header: data rows may use decimal commas, headers never do
        sep = ";" if ";" in header else ("\t" if "\t" in header else ",")
        # European decimal comma: "1,23;4,56"
        decimal = "," if sep == ";" and re.search(r"\d,\d", text) else "."
        df = pd.read_csv(io.StringIO(text), sep=sep, decimal=decimal)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df


def _unit_in_header(header: str, units: list[str]) -> str | None:
    h = header.lower().replace("µ", "u").replace("μ", "u")
    for u in sorted(units, key=len, reverse=True):
        if re.search(rf"[\(\[\s_]{re.escape(u.lower())}[\)\]\s]*$", h) or h.endswith(u.lower()):
            return u
    return None


def suggest_mapping(df: pd.DataFrame, spec: DatasetSpec) -> dict:
    headers = [str(c) for c in df.columns]
    mapping, used = {}, set()
    for col in spec.columns:
        best = None
        for h in headers:
            if h in used:
                continue
            hl = f" {h.lower()} "
            if any(a in hl for a in col.aliases):
                best = h
                break
        if best is None:                      # fall back to column order
            free = [h for h in headers if h not in used]
            best = free[0] if free else None
        if best is not None:
            used.add(best)
        mapping[col.key] = {"header": best,
                            "unit": (_unit_in_header(best, col.units) if best else None) or col.units[0]}
    return {"headers": headers, "mapping": mapping, "preview": df.head(8).astype(str).values.tolist()}


def extract(df: pd.DataFrame, spec: DatasetSpec, mapping: dict) -> tuple[dict[str, list[float]], list[str]]:
    """Return canonical-unit columns (sorted by the first column) and notes."""
    out, notes = {}, []
    for col in spec.columns:
        m = mapping[col.key]
        series = pd.to_numeric(df[m["header"]], errors="coerce")
        unit = m["unit"]
        if col.key == "T" and unit == "C":
            vals = (series + 273.15).tolist()
            notes.append("Temperature converted from degrees C to K.")
        else:
            f = TO_CANONICAL.get(unit, 1.0)
            vals = (series * f).tolist()
            if f != 1.0:
                notes.append(f"{col.label} converted from {unit} to {col.units[0]}.")
        out[col.key] = vals
    keys = list(out)
    rows = [r for r in zip(*(out[k] for k in keys)) if all(pd.notna(v) for v in r)]
    dropped = len(df) - len(rows)
    if dropped:
        notes.append(f"{dropped} row(s) with missing or non-numeric values were skipped.")
    rows.sort(key=lambda r: r[0])
    if len(rows) < spec.min_rows:
        raise ValueError(f"Need at least {spec.min_rows} usable rows, found {len(rows)}.")
    if any(r[0] <= 0 for r in rows) and spec.columns[0].key == "conc":
        raise ValueError("Concentrations must be positive (they are used on a log scale).")
    return {k: [r[i] for r in rows] for i, k in enumerate(keys)}, notes
