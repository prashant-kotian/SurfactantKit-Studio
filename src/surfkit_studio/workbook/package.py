"""Filled workbook in, ZIP out: completed workbook, every plot as PNG and xmgrace .agr."""
from __future__ import annotations

import io
import zipfile

from .analysis import analyse
from .figures import build_figs, render_agr, render_png
from .reader import read_workbook
from .writer import write_output


def build_output_zip(data: bytes, stem: str = "surfactant_study") -> tuple[bytes, dict]:
    """Returns the ZIP and a short summary (for the web page)."""
    study = read_workbook(data)
    res = analyse(study)
    figs = build_figs(study, res)
    pngs = [(f.name, render_png(f)) for f in figs]
    xlsx = write_output(study, res, pngs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{stem}_results.xlsx", xlsx)
        for f, (_, png) in zip(figs, pngs):
            z.writestr(f"plots/{f.name}.png", png)
            z.writestr(f"plots/{f.name}.agr", render_agr(f))
        z.writestr("README.txt",
                   "Completed workbook: Results sheets, Excel Solver sheets (Rubingh per composition, Rubingh "
                   "global, Rosen per composition) with the Solver model preset, Comparison, Flags, Plots, Methods.\n"
                   "plots/*.png: figures. plots/*.agr: the same figures as xmgrace (Grace) projects, open with "
                   "xmgrace or QtGrace to edit.\n")
    summary = {
        "beta_m_mean": res.rubingh.get("beta_mean"), "beta_m_global": res.rubingh.get("beta_global"),
        "beta_sigma_mean": res.rosen.get("beta_mean"),
        "cmc": {p["name"]: p.get("cmc_t") for p in res.pure},
        "n_mixtures": len(res.mix_rows), "n_flags": len([f for f in res.flags if f.level == "warning"]),
        "flags": [f"{f.where}: {f.message}" for f in res.flags if f.level == "warning"],
        "n_plots": len(figs),
    }
    return buf.getvalue(), summary
