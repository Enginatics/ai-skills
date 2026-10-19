"""Build a Blitz Report import XML: python build_xml.py <spec.py> <out.xml>

spec.py defines CATEGORY and either REPORTS (a list of report dicts - the category deliverable, every
report plus all their assignments in one file) or the keys of a single report at top level.
A report dict: NAME, DESCRIPTION, SQL (path), GUID, ASSIGNMENTS (the converter's _assignments.xml), PARAMS,
SHORT_NAME (the short name of the program the report replaces, the view name for a custom view) and optional PROGRAM
(its user-visible name), optional NUMBER_FORMAT (default #,##0.00;[Red]-#,##0.00; 'General' prints numbers as the original prints them),
optional TEMPLATES and DEFAULT_TEMPLATE (the name of the template every user gets without choosing one).

PARAMS lists one dict per PARAMETERS_ROW, in order:
  name, anchor, sql       sql is the SQL_TEXT; omit it for a :bind anchor
  type                    Date, Char, Number, LOV (shared Blitz LOV), LOV Oracle (value set), LOV custom
  lov, lov_query          LOV / LOV Oracle name, LOV custom query
  fbd                     LOV custom only: filter before display (a list too long to download, e.g. all suppliers)
  required, default       REQUIRED=Y, DEFAULT_VALUE
  description             the run screen tooltip (US translation row)
  matching                MATCHING_VALUE
  hidden                  negative DISPLAY_SEQUENCE
  display_sequence        explicit DISPLAY_SEQUENCE, to show a parameter elsewhere on the run screen without moving its
                          SORT_ORDER (the import's upsert key)
  sub                     a further anchor of the same parameter: no display sequence, type, LOV, default or required
  lexical                 anchor '&name' placed where the fragment goes; sql is a select returning one line per fragment
                          row (the engine substitutes all rows); hidden + a constant default so the value is always set
Shared-LOV fallback payloads (LOV_GUID, FILTER_BEFORE_DISPLAY_DSP, LOV_QUERY_DSP) are copied from the shipped content
(the repository's content/r12/reports, or the folder of report XMLs named by the BLITZ_CONTENT_DIR environment variable).
"""
import collections
import glob
import html
import os
import re
import runpy
import sys

REPO = os.path.join(os.environ.get("BLITZ_CONTENT_DIR") or os.path.join(os.path.dirname(__file__), "..", "..", "..", "content", "r12", "reports"), "")
SQL_FUNCTIONS = {"abs", "add_months", "bitand", "cast", "ceil", "chr", "coalesce", "decode", "greatest", "initcap", "instr", "last_day", "least", "length",
                 "lower", "lpad", "mod", "months_between", "next_day", "nvl", "nvl2", "power", "regexp_replace", "regexp_substr", "replace", "round", "rtrim",
                 "sign", "substr", "substrb", "to_char", "to_date", "to_number", "translate", "trim", "trunc", "upper", "userenv"}


def shared_lov(name):
    for p in glob.glob(REPO + "*.xml"):
        s = open(p, encoding="utf-8").read()
        m = re.search(r"<LOV_NAME>" + re.escape(name) + r"</LOV_NAME>\s*<LOV_GUID>(\w+)</LOV_GUID>\s*(?:<FREE_TEXT>\w</FREE_TEXT>\s*)?(<FILTER_BEFORE_DISPLAY_DSP>\w</FILTER_BEFORE_DISPLAY_DSP>\s*)?<LOV_QUERY_DSP>(.*?)</LOV_QUERY_DSP>", s, re.S)
        if m:
            return m.group(1), (m.group(2) or "").strip(), m.group(3)
    raise SystemExit("shared LOV not found: " + name)


def e(t):
    return html.escape(t, quote=False).replace("'", "&apos;")


def param_rows(rep):
    rows, visible = [], 0
    for i, p in enumerate(rep["PARAMS"], 1):
        r = [f"<SORT_ORDER>{i}</SORT_ORDER>"]
        if not p.get("sub"):
            visible += 1
            r.append(f"<DISPLAY_SEQUENCE>{p.get('display_sequence') or (-visible * 10 if p.get('hidden') else visible * 10)}</DISPLAY_SEQUENCE>")
        r.append(f"<ANCHOR>{e(p['anchor'])}</ANCHOR>")
        if p.get("sql"):
            r.append(f"<SQL_TEXT>{e(p['sql'])}</SQL_TEXT>")
        if not p.get("sub"):
            r.append(f"<PARAMETER_TYPE_DSP>{p['type']}</PARAMETER_TYPE_DSP>")
            if p["type"] == "LOV":
                guid, fbd, q = shared_lov(p["lov"])
                r += [f"<LOV_NAME>{e(p['lov'])}</LOV_NAME>", f"<LOV_GUID>{guid}</LOV_GUID>"] + ([fbd] if fbd else []) + [f"<LOV_QUERY_DSP>{q}</LOV_QUERY_DSP>"]
            elif p["type"] == "LOV Oracle":
                r += [f"<LOV_NAME>{e(p['lov'])}</LOV_NAME>"]
            elif p["type"] == "LOV custom":
                r += (["<FILTER_BEFORE_DISPLAY_DSP>Y</FILTER_BEFORE_DISPLAY_DSP>"] if p.get("fbd") else []) + [f"<LOV_QUERY_DSP>{e(p['lov_query'].strip())}</LOV_QUERY_DSP>"]
        if p.get("matching"):
            r.append(f"<MATCHING_VALUE>{e(p['matching'])}</MATCHING_VALUE>")
        if not p.get("sub"):
            if p.get("default"):
                r.append(f"<DEFAULT_VALUE>{e(p['default'])}</DEFAULT_VALUE>")
            if p.get("required"):
                r.append("<REQUIRED>Y</REQUIRED>")
        description = f"\n      <DESCRIPTION>{e(p['description'])}</DESCRIPTION>" if p.get("description") and not p.get("sub") else ""
        r.append(f"<PARAMETER_TRANSLATIONS>\n     <PARAMETER_TRANSLATIONS_ROW>\n      <LANGUAGE>US</LANGUAGE>\n      <PARAMETER_NAME>{e(p['name'])}</PARAMETER_NAME>{description}\n     </PARAMETER_TRANSLATIONS_ROW>\n    </PARAMETER_TRANSLATIONS>")
        rows.append("   <PARAMETERS_ROW>\n    " + "\n    ".join(r) + "\n   </PARAMETERS_ROW>")
    return rows


def select_aliases(sql):
    """output column names: the trailing identifier of every depth-0 item of the top-level select list"""
    items, cur, depth, started = [], [], 0, False
    for t in re.findall(r"'(?:[^']|'')*'|\"[^\"]*\"|--[^\n]*|/\*.*?\*/|[(),]|[\w$#&:.]+|\S", sql, re.S):
        low = t.lower()
        if low.startswith(("--", "/*")):
            continue
        if not started:
            started = low == "select"
            continue
        if t == "(":
            depth += 1
        elif t == ")":
            depth -= 1
        elif depth == 0 and t == ",":
            items.append(cur)
            cur = []
            continue
        elif depth == 0 and low == "from":
            break
        cur.append(t)
    items.append(cur)
    return [i[-1].rsplit(".", 1)[-1].strip('"').lower() for i in items if i]


def check(rep, sql):
    # an alias is the column heading: RDF formula, placeholder and summary names must be renamed after the layout heading
    rdf = [a for a in select_aliases(sql) if re.match(r"c[fps]_", a)]
    if rdf:
        raise SystemExit(f"{rep['NAME']}: RDF column names in the select list, name them after the layout heading: {rdf}")
    display = collections.Counter(p["name"] for p in rep["PARAMS"] if not p.get("sub"))
    for name in {p["name"] for p in rep["PARAMS"]}:
        if display[name] != 1:
            raise SystemExit(f"{rep['NAME']}: parameter {name} has {display[name]} display rows")
    for a in {p["anchor"] for p in rep["PARAMS"]}:
        n = len(re.findall(r"(?<![\w&:])" + re.escape(a) + r"(?!\w)", sql, re.I))
        # the framework injects an n=n parameter at EVERY occurrence of its anchor; a report that wants the
        # filters inside each union branch declares the intended count as REPEATED_ANCHOR (anchor -> count)
        expected = rep.get("REPEATED_ANCHOR", {}).get(a, 1)
        if n == 0 or re.fullmatch(r"(\d+)=\1", a) and n != expected:
            raise SystemExit(f"{rep['NAME']}: anchor {a} occurs {n} times in the SQL, expected {expected}")
    # the run form wraps a custom list as select null id, x.value, x.description from (<query>) x
    for p in rep["PARAMS"]:
        q = p.get("lov_query")
        if q and not (re.search(r"\bvalue\b", q, re.I) and re.search(r"\bdescription\b", q, re.I)):
            raise SystemExit(f"{rep['NAME']}: LOV custom of {p['name']} must return value and description columns")
    # the import stores filter before display only for a custom list: a value set's comes from its Long List flag, a shared list's from the list
    for p in rep["PARAMS"]:
        if p.get("fbd") and p.get("type") != "LOV custom":
            raise SystemExit(f"{rep['NAME']}: fbd on {p['name']} needs type LOV custom, the import ignores it for {p.get('type')}")
    # xxen_report.is_function: a default that is neither a select nor one of these expressions is stored as a literal
    for p in rep["PARAMS"]:
        d = (p.get("default") or "").strip()
        c = re.sub(r"\s", "", d).lower()
        f = re.match(r"(\w+)\(", c)
        evaluated = re.match(r"(select|with)\b", d, re.I) or re.match(r"(xxen_report\w*|xxen_schub|xxen_util|fnd_global|fnd_profile|:\$flex\$)\.|sys_context\(", c) \
            or f and f.group(1) in SQL_FUNCTIONS or c.startswith("sysdate") and p.get("type", "").startswith("Date") or re.fullmatch(r"case\s.*\send", d, re.I | re.S)
        if d and not evaluated and (re.fullmatch(r"[a-z_][\w$#]*\.[a-z_][\w$#]*(\(.*\))?", c) or p.get("type") == "Number" and not re.fullmatch(r"-?\d+(\.\d+)?", d)):
            raise SystemExit(f"{rep['NAME']}: default of {p['name']} would be stored as the literal text '{d}', write it as select ... from dual")


def template_rows(rep):
    """TEMPLATES_ROW per entry of the report's TEMPLATES list: NAME, GUID, COLUMNS (ordered column names),
    PIVOT (list of (column, ROW|COLUMN|VALUE|FILTER[, aggregation])), optional DYNAMIC_COLUMNS (default N),
    PIVOT_LAYOUT (T = tabular, no subtotals) and REPEAT_LABELS (Y = every row shows all its row field values),
    SHARED (default True: a Site sharing row, so every user of the report can pick it), DISTINCT (Y = one row per distinct
    combination of the template's columns) and EXCLUDED_PARAMETERS (parameters hidden and not applied when the template is chosen).
    A layout on a NEW report ships inside its definition; the standalone template file is only for a shipped report."""
    out = []
    for t in rep.get("TEMPLATES", []):
        cols = "\n".join(f"     <TEMPLATE_COLUMNS_ROW>\n      <DISPLAY_SEQUENCE>{i}</DISPLAY_SEQUENCE>\n      <COLUMN_NAME>{e(c)}</COLUMN_NAME>\n     </TEMPLATE_COLUMNS_ROW>"
                         for i, c in enumerate(t["COLUMNS"], 1))
        seq = collections.Counter()
        piv = []
        for row in t.get("PIVOT", []):
            col, ftype = row[0], row[1]
            seq[ftype] += 1
            agg = f"\n      <AGGREGATION>{row[2]}</AGGREGATION>" if len(row) > 2 else ""
            piv.append(f"     <TEMPLATE_PIVOT_ROW>\n      <COLUMN_NAME>{e(col)}</COLUMN_NAME>\n      <FIELD_TYPE>{ftype}</FIELD_TYPE>\n      <DISPLAY_SEQUENCE>{seq[ftype]}</DISPLAY_SEQUENCE>{agg}\n     </TEMPLATE_PIVOT_ROW>")
        missing = {r[0] for r in t.get("PIVOT", [])} - set(t["COLUMNS"])
        if missing:
            raise SystemExit(f"{rep['NAME']}/{t['NAME']}: pivot columns not in TEMPLATE_COLUMNS: {sorted(missing)}")
        pivot = f"\n    <TEMPLATE_PIVOT>\n{chr(10).join(piv)}\n    </TEMPLATE_PIVOT>" if piv else ""
        pivot += "".join(f"\n    <{k}>{t[k]}</{k}>" for k in ("PIVOT_LAYOUT", "REPEAT_LABELS") if t.get(k))
        unknown = set(t.get("EXCLUDED_PARAMETERS", [])) - {p["name"] for p in rep["PARAMS"]}
        if unknown:
            raise SystemExit(f"{rep['NAME']}/{t['NAME']}: excluded parameters not in PARAMS: {sorted(unknown)}")
        if t.get("EXCLUDED_PARAMETERS"):
            pivot += "\n    <PARAMETER_EXCLUSION>" + "".join(f"\n     <PARAMETER_EXCLUSION_ROW>\n      <PARAMETER_NAME>{e(n)}</PARAMETER_NAME>\n     </PARAMETER_EXCLUSION_ROW>"
                                                   for n in t["EXCLUDED_PARAMETERS"]) + "\n    </PARAMETER_EXCLUSION>"
        # without a sharing row only the owner can pick the template
        sharing = ("\n    <TEMPLATE_SHARING>\n     <TEMPLATE_SHARING_ROW>\n      <SHARING_LEVEL>S</SHARING_LEVEL>\n"
                   "      <LEVEL_VALUE>Site</LEVEL_VALUE>\n     </TEMPLATE_SHARING_ROW>\n    </TEMPLATE_SHARING>") if t.get("SHARED", True) else ""
        out.append(f"""   <TEMPLATES_ROW>
    <GUID>{t['GUID']}</GUID>
    <TEMPLATE_NAME>{e(t['NAME'])}</TEMPLATE_NAME>{chr(10) + '    <DISTINCT_FLAG>Y</DISTINCT_FLAG>' if t.get('DISTINCT') == 'Y' else ''}
    <DYNAMIC_COLUMNS>{t.get('DYNAMIC_COLUMNS', 'N')}</DYNAMIC_COLUMNS>
    <OWNER>SYSADMIN</OWNER>
    <TEMPLATE_COLUMNS>
{cols}
    </TEMPLATE_COLUMNS>{pivot}{sharing}
   </TEMPLATES_ROW>""")
    return out


def description(rep):
    # the program link in the format of Blitz Report's own concurrent program import; the migration tracker reads it
    if not rep.get("SHORT_NAME"):
        raise SystemExit(f"{rep['NAME']}: SHORT_NAME, the short name of the program the report replaces, is required")
    source = f"Source: {rep['PROGRAM']}\n" if rep.get("PROGRAM") else ""
    return f"{rep['DESCRIPTION'].rstrip()}\n\n{source}Short Name: {rep['SHORT_NAME']}"


def report_xml(rep, category):
    sql = open(rep["SQL"], encoding="utf-8").read().replace("\r\n", "\n").strip()
    check(rep, sql)
    anchors = sorted({p["anchor"] for p in rep["PARAMS"]})
    rows = param_rows(rep)
    templates = template_rows(rep)
    # a DEFAULT_TEMPLATES_ROW without USER_NAME is the global default; it applies only to users who can use the template
    default = ""
    if rep.get("DEFAULT_TEMPLATE"):
        t = next((t for t in rep.get("TEMPLATES", []) if t["NAME"] == rep["DEFAULT_TEMPLATE"]), None)
        if not t or not t.get("SHARED", True):
            raise SystemExit(f"{rep['NAME']}: default template {rep['DEFAULT_TEMPLATE']} must be one of its TEMPLATES and shared")
        default = f"\n   <DEFAULT_TEMPLATES_ROW>\n    <TEMPLATE_GUID>{t['GUID']}</TEMPLATE_GUID>\n   </DEFAULT_TEMPLATES_ROW>"
    return f"""<!-- loader xml for Blitz Report: {e(rep['NAME'])} -->
 <REPORTS_ROW>
  <GUID>{rep['GUID']}</GUID>
  <SQL_TEXT>{e(sql)}</SQL_TEXT>
  <NUMBER_FORMAT>{e(rep.get('NUMBER_FORMAT', '#,##0.00;[Red]-#,##0.00'))}</NUMBER_FORMAT>
  <REPORT_TRANSLATIONS>
   <REPORT_TRANSLATIONS_ROW>
    <LANGUAGE>US</LANGUAGE>
    <REPORT_NAME>{e(rep['NAME'])}</REPORT_NAME>
    <DESCRIPTION>{e(description(rep))}</DESCRIPTION>
   </REPORT_TRANSLATIONS_ROW>
  </REPORT_TRANSLATIONS>
  <CATEGORY_ASSIGNMENTS>
   <CATEGORY_ASSIGNMENTS_ROW>
    <CATEGORY>{e(category)}</CATEGORY>
   </CATEGORY_ASSIGNMENTS_ROW>
  </CATEGORY_ASSIGNMENTS>
  <ANCHORS>
{chr(10).join(f"   <ANCHORS_ROW>{chr(10)}    <ANCHOR>{e(a)}</ANCHOR>{chr(10)}   </ANCHORS_ROW>" for a in anchors)}
  </ANCHORS>
  <PARAMETERS>
{chr(10).join(rows)}
  </PARAMETERS>
  <TEMPLATES>
{chr(10).join(templates)}
  </TEMPLATES>
  <DEFAULT_TEMPLATES>{default}
  </DEFAULT_TEMPLATES>
  <UPLOAD_COLUMNS>
  </UPLOAD_COLUMNS>
  <UPLOAD_PARAMETERS>
  </UPLOAD_PARAMETERS>
  <UPLOAD_SQLS>
  </UPLOAD_SQLS>
 </REPORTS_ROW>""", len(rows)


def assignment_rows(rep):
    asg = open(rep["ASSIGNMENTS"], encoding="utf-8").read()
    return [r.replace("<ASSIGNMENTS_ROW>", f"<ASSIGNMENTS_ROW><REPORT_NAME>{e(rep['NAME'])}</REPORT_NAME>")
            for r in re.findall(r"<ASSIGNMENTS_ROW>.*?</ASSIGNMENTS_ROW>", asg, re.S)]


spec = runpy.run_path(sys.argv[1])
category = spec["CATEGORY"]
reports = spec.get("REPORTS") or [spec]
blocks, asg = [], []
for rep in reports:
    block, n = report_xml(rep, category)
    blocks.append(block)
    asg += assignment_rows(rep)
    print(f"  {rep['NAME']}: {n} parameter rows, {len(assignment_rows(rep))} assignments")

out = f"""<ROOT>
 <APPS_INITIALIZE_DATA>
  <USER_NAME>ENGINATICS</USER_NAME>
  <RESPONSIBILITY_KEY>SYSTEM_ADMINISTRATOR</RESPONSIBILITY_KEY>
  <APPLICATION_SHORT_NAME>SYSADMIN</APPLICATION_SHORT_NAME>
 </APPS_INITIALIZE_DATA>
<CATEGORIES>
 <CATEGORIES_ROW>
  <BASE_CATEGORY>{e(category)}</BASE_CATEGORY>
  <CATEGORY_TRANSLATIONS>
   <CATEGORY_TRANSLATIONS_ROW>
    <LANGUAGE>US</LANGUAGE>
    <CATEGORY>{e(category)}</CATEGORY>
   </CATEGORY_TRANSLATIONS_ROW>
  </CATEGORY_TRANSLATIONS>
 </CATEGORIES_ROW>
</CATEGORIES>
<REPORTS>
{chr(10).join(blocks)}
</REPORTS>
<ASSIGNMENTS>
{chr(10).join(' ' + r for r in asg)}
</ASSIGNMENTS>
</ROOT>
"""
open(sys.argv[2], "w", encoding="utf-8", newline="\r\n").write(out)
print("wrote", sys.argv[2], len(out), "bytes,", len(reports), "reports,", len(asg), "assignments")
