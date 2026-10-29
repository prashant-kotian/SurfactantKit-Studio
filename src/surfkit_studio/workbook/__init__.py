"""Workbook mode: a downloadable Excel template for a binary surfactant study, read back after
the researcher fills it in, analysed with SurfactantKit, and returned as a completed workbook
(results, live Excel-Solver sheets beside the toolkit's own values, a comparison sheet, flags)
with every plot as PNG and xmgrace .agr.
"""
from .analysis import analyse
from .package import build_output_zip
from .reader import WorkbookError, read_workbook
from .template import build_template

__all__ = ["build_template", "read_workbook", "analyse", "build_output_zip", "WorkbookError"]
