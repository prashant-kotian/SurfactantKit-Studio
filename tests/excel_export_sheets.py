"""Visual check (Windows + Excel): export chosen sheets of a workbook to one PDF.
Usage: python excel_export_sheets.py <xlsx> <out.pdf> "Sheet A" "Sheet B" ..."""
import os
import sys

import win32com.client as win32

src, out, *names = sys.argv[1:]
xl = win32.DispatchEx("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False
try:
    wb = xl.Workbooks.Open(os.path.abspath(src), 0, True)
    for n in names:
        ws = wb.Worksheets(n)
        ws.PageSetup.Orientation = 2          # landscape
        ws.PageSetup.Zoom = False
        ws.PageSetup.FitToPagesWide = 1
        ws.PageSetup.FitToPagesTall = False
    wb.Worksheets(names).Select()
    xl.ActiveSheet.ExportAsFixedFormat(0, os.path.abspath(out))
    wb.Close(False)
finally:
    xl.Quit()
