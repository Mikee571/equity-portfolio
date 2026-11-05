"""Prints the key outputs of adobe_dcf.xlsx after it has been recalculated in Excel, and checks for formula errors."""
from openpyxl import load_workbook
wb = load_workbook("adobe_dcf.xlsx", data_only=True); wf = load_workbook("adobe_dcf.xlsx")
n = sum(1 for ws in wf.worksheets for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("="))
errs = [(ws.title, c.coordinate) for ws in wf.worksheets for row in ws.iter_rows() for c in row
        if isinstance(c.value, str) and c.value.startswith("=") and (wb[ws.title][c.coordinate].value is None
        or (isinstance(wb[ws.title][c.coordinate].value, str) and wb[ws.title][c.coordinate].value.startswith("#")))]
print(f"{n} formulas, errors or empty: {errs or 'none'}")
s = wb["Summary"]
fmt = lambda v: ("%11.1f%%" % (v * 100)) if isinstance(v, float) and abs(v) < 1.5 else (f"{v:>12,.1f}" if isinstance(v, (int, float)) else f"{'':>12s}")
for r in list(range(4, 15)) + list(range(16, 22)):
    print(f"{str(s.cell(r, 1).value):58s}", *[fmt(s.cell(r, k).value) for k in range(2, 7)])
d = wb["DCF"]
for top in (3, 39):
    print(d.cell(top, 1).value)
    for r in range(top + 2, top + 13):
        print(f"{str(d.cell(r, 1).value):42s}", *[f"{(d.cell(r, k).value or 0):8.3f}" if abs(d.cell(r, k).value or 0) < 2 else f"{(d.cell(r, k).value or 0):8.0f}" for k in range(3, 13)])
rv = wb["Reverse DCF"]
for r in (7, 13, 14, 15):
    print(rv.cell(r, 1).value, round(rv.cell(r, 3).value, 4))
for r in list(range(21, 31)) + list(range(34, 40)):
    print([rv.cell(r, 1).value] + [round(rv.cell(r, k).value, 3) if isinstance(rv.cell(r, k).value, float) else rv.cell(r, k).value for k in range(3, 10)])
