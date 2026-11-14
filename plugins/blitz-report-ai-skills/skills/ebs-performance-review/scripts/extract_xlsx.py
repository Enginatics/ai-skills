"""Turn the Blitz Report DBA extracts into JSON for analysis.

usage: python extract_xlsx.py <folder-with-xlsx> <output-folder>

Produces awr.json, sga.json (one dict per row, keyed by column header) and
src_<n>.json for every DBA Text Search export ({"OWNER|TYPE|NAME": {line: text}}).
File names are matched on their Blitz Report name prefix, so the timestamp suffix
does not matter.
"""
import glob
import json
import os
import sys

import openpyxl


def read_sheet(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    wb.close()
    hdr = [str(h).strip() if h is not None else "" for h in rows[0]]
    return [{h: r[i] if i < len(r) else None for i, h in enumerate(hdr) if h} for r in rows[1:]]


def read_source(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    src = {}
    # an export over the Excel row limit continues on further sheets (<name>_2, ...)
    for ws in wb.worksheets:
        if ws.title == "Parameters":
            continue
        for n, r in enumerate(ws.iter_rows(values_only=True)):
            if n == 0 or r[2] is None:
                continue
            owner, typ, name, line, text = r[:5]
            src.setdefault(f"{owner}|{typ}|{name}", {})[int(line)] = (text or "").rstrip("\n")
    wb.close()
    return src


if __name__ == "__main__":
    base, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for prefix, target in (("DBA AWR SQL Performance Summary", "awr.json"),
                           ("DBA SGA SQL Performance Summary", "sga.json")):
        for p in glob.glob(os.path.join(base, prefix + "*.xlsx")):
            rows = read_sheet(p)
            json.dump(rows, open(os.path.join(out, target), "w", encoding="utf-8"), default=str, indent=1)
            print(target, len(rows), "rows from", os.path.basename(p))
    for n, p in enumerate(sorted(glob.glob(os.path.join(base, "DBA Text Search*.xlsx"))), 1):
        src = read_source(p)
        json.dump(src, open(os.path.join(out, f"src_{n}.json"), "w", encoding="utf-8"), indent=0)
        print(f"src_{n}.json", len(src), "objects from", os.path.basename(p))
