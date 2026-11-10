"""Generate <PKG>.pkb (verbatim) and <PKG>_corrected.pkb for every
package in EDITS, from the DBA Text Search JSON produced by extract_xlsx.py.

Edits are line-range replacements against the ORIGINAL line numbers, so every
line outside a range is provably untouched. Each entry is
(first_line, last_line, replacement_lines); last_line < first_line inserts
before first_line. Deleting is an empty replacement list.

Match the customer's code style in replacements. Comments say why the code is
shaped as it is, never what changed.
"""
import difflib
import glob
import json
import os

WORK = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(WORK, "pairs")

SRC = {}
for f in glob.glob(os.path.join(WORK, "src_*.json")):
    for k, v in json.load(open(f, encoding="utf-8")).items():
        owner, typ, name = k.split("|")
        if typ == "PACKAGE BODY":
            SRC.setdefault(name, {int(a): b for a, b in v.items()})

EDITS = {
    # "XX_SOME_PKG": [
    #     (84, 85, ["      delete bom_explosion_temp where group_id = wbill_sequence_id;"]),
    #     (122, 121, ["", "   -- inserted before line 122"]),
    # ],
}


def body(name):
    d = SRC[name]
    return [d[i] for i in range(1, max(d) + 1)]


def apply_edits(lines, edits):
    out = list(lines)
    for first, last, repl in sorted(edits, key=lambda e: -e[0]):
        if last < first:
            out[first - 1:first - 1] = repl
        else:
            out[first - 1:last] = repl
    return out


def write(path, lines):
    text = "CREATE OR REPLACE " + lines[0] + "\n" + "\n".join(lines[1:]) + "\n/\n"
    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(text)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, edits in EDITS.items():
        orig = body(name)
        corr = apply_edits(orig, edits)
        write(os.path.join(OUT, f"{name}.pkb"), orig)
        write(os.path.join(OUT, f"{name}_corrected.pkb"), corr)
        diff = list(difflib.unified_diff(orig, corr, lineterm="", n=3))
        hunks = sum(1 for l in diff if l.startswith("@@"))
        print(f"  {name:<32} {len(orig):>6} -> {len(corr):<6} {hunks} hunks")
