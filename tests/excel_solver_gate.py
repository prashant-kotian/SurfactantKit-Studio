"""Gate (Windows + Excel only, not part of pytest): open a Studio output workbook in real Excel, run the
preset Solver model on each Solver sheet without touching its settings, and print the Comparison sheet.
Usage: python excel_solver_gate.py <results.xlsx> [<solved_copy.xlsx>]
"""
import os
import sys
import time

import win32com.client as win32

SHEETS = ["Rubingh per-point (Solver)", "Rubingh global (Solver)", "Rosen per-point (Solver)"]


def main(path, out=None):
    path = os.path.abspath(path)
    xl = win32.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    try:
        addin = os.path.join(xl.LibraryPath, "SOLVER", "SOLVER.XLAM")
        xl.Workbooks.Open(addin)
        xl.Run("Solver.xlam!Auto_open")
        wb = xl.Workbooks.Open(path)
        for name in SHEETS:
            try:
                ws = wb.Worksheets(name)
            except Exception:
                print(f"{name}: not in workbook"); continue
            ws.Activate()
            t0 = time.time()
            code = xl.Run("Solver.xlam!SolverSolve", True)
            print(f"{name}: SolverSolve returned {code} in {time.time() - t0:.1f} s")
        xl.CalculateFull()
        cmp_ = wb.Worksheets("Comparison")
        r = 5
        while cmp_.Cells(r, 1).Value:
            vals = [cmp_.Cells(r, c).Value for c in range(1, 7)]
            print(" | ".join(f"{v:.5f}" if isinstance(v, float) else str(v) for v in vals))
            r += 1
        if out:
            wb.SaveAs(os.path.abspath(out))
        wb.Close(False)
    finally:
        xl.Quit()


if __name__ == "__main__":
    main(*sys.argv[1:])
