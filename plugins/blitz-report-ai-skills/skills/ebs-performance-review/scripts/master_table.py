"""Build the section-1 table of the review: one row per problem, ordered by cost.

Percentages come from awr.json (sum of Percentage per sql_id, each sql_id counted
once). Fill ROWS with the analyst's judgement. Output is frag_master.html, to be
included in the report where <!--MASTER_TABLE--> stands.

Status must say whether code is supplied:
  done   Corrected     a corrected package body is in package_code/
  rec    Recommended   described only: DBA action, setup, or code outside the database
  input  Needs input   the fix needs a run from the customer; say which in section 3
  none   Not analysed  source not supplied
"""
import collections
import html
import json

ST = {
    "done": ("Corrected", "st-done", "A corrected package body is supplied. Compile and test it."),
    "rec": ("Recommended", "st-rec", "Described only: a DBA action, a setup change, or code outside the database."),
    "input": ("Needs input", "st-input", "The fix needs a run from you. Section 3 says which."),
    "none": ("Not analysed", "st-none", "The source was not in the extracts supplied."),
}

CSS = """.st-done{background:#1e8449}.st-rec{background:#2471a3}.st-input{background:#b9770e}.st-none{background:#c0392b}
.sid{display:inline-block;font-family:Consolas,monospace;font-size:11px;padding:1px 5px;border-radius:3px;color:#fff;margin-bottom:2px}
.tag{display:inline-block;font-size:11px;font-weight:bold;padding:1px 6px;border-radius:3px;color:#fff;white-space:nowrap}
table.master td{vertical-align:top;font-size:12.5px}table.master th{font-size:12px}"""

# (sql_ids, where, defect, change, status, file)
ROWS = [
    # (["cyz8xf1a7mwqh"], "XX_PKG", "what is wrong, 1-3 sentences", "what changes, 1-3 sentences", "done", "XX_PKG_corrected.pkb"),
]


def build(awr="awr.json"):
    pct = collections.defaultdict(float)
    for r in json.load(open(awr, encoding="utf-8")):
        if r.get("Sql Id"):
            pct[r["Sql Id"]] += float(r.get("Percentage") or 0)
    counted, items = set(), []
    for ids, where, defect, change, st, f in ROWS:
        share = sum(pct.get(s, 0.0) for s in ids if s not in counted)
        counted.update(ids)
        items.append([share, ids, where, defect, change, st, f])
    top40 = {s for s, _ in sorted(pct.items(), key=lambda kv: -kv[1])[:40]}
    for it in items:
        if it[5] == "none":
            it[0] = sum(pct[s] for s in top40 - counted)
    items.sort(key=lambda x: -x[0])

    band, cnt = collections.defaultdict(float), collections.Counter()
    for share, _i, _w, _d, _c, st, _f in items:
        band[st] += share
        cnt[st] += 1
    out = ['<table><thead><tr><th>Status</th><th>% DB CPU</th><th>Rows</th><th>Meaning</th></tr></thead><tbody>']
    for st in ("done", "rec", "input", "none"):
        label, cls, meaning = ST[st]
        out.append(f'<tr><td><span class="tag {cls}">{label}</span></td><td class="n">{band[st]:.2f}</td>'
                   f'<td class="n">{cnt[st]}</td><td>{meaning}</td></tr>')
    out.append('</tbody></table>\n<table class="master"><thead><tr><th>sql_id</th><th>% DB CPU</th><th>Where</th>'
               '<th>The defect</th><th>The change</th><th>Status</th></tr></thead><tbody>')
    for share, ids, where, defect, change, st, f in items:
        label, cls, _ = ST[st]
        sids = "<br>".join(f'<span class="sid {cls}">{i}</span>' for i in ids) or '<span class="small">several</span>'
        fileline = f'<br><span class="small">File: <code>{html.escape(f)}</code></span>' if f else ""
        out.append(f'<tr><td>{sids}</td><td class="n">{share:.2f}</td><td class="small">{html.escape(where)}</td>'
                   f'<td>{html.escape(defect)}</td><td>{html.escape(change)}{fileline}</td>'
                   f'<td><span class="tag {cls}">{label}</span></td></tr>')
    out.append('</tbody></table>')
    return "\n".join(out)


if __name__ == "__main__":
    open("frag_master.html", "w", encoding="utf-8", newline="\n").write(build())
    print("frag_master.html written; add this CSS to the report head:\n" + CSS)
