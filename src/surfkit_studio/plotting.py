"""Figure helpers: one quiet house style (Paper 3's), PNG bytes out.

Labels use plain keyboard characters (no Greek glyphs) so figures drop
straight into reports that follow the manuscript formatting spec.
"""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK = "#1f2328"
MUTED = "#6e7781"
DATA = "#0072B2"      # Okabe-Ito blue: measured points
FIT = "#D55E00"       # Okabe-Ito vermillion: fitted model
ALT = "#009E73"       # Okabe-Ito green: second model / cross-check
MARK = "#CC79A7"      # Okabe-Ito purple: the derived quantity (CMC line etc.)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
    "font.size": 9,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "legend.frameon": False,
    "axes.unicode_minus": False,
})


def new(width_cm: float = 12.0, height_cm: float = 8.0):
    fig, ax = plt.subplots(figsize=(width_cm / 2.54, height_cm / 2.54), dpi=150)
    return fig, ax


def to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=200)
    plt.close(fig)
    return buf.getvalue()
