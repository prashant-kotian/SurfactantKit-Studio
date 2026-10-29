"""Probe (Windows + Excel): which file opens in real Excel. Usage: python excel_open_probe.py <xlsx>..."""
import os
import sys

import win32com.client as win32

xl = win32.DispatchEx("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False
try:
    for p in sys.argv[1:]:
        try:
            wb = xl.Workbooks.Open(os.path.abspath(p), 0, True)
            print("OPEN OK ", p, [s.Name for s in wb.Worksheets][:4], "...")
            wb.Close(False)
        except Exception as e:  # noqa: BLE001
            print("OPEN FAIL", p, e.args[2][2] if len(e.args) > 2 and e.args[2] else e)
finally:
    xl.Quit()
