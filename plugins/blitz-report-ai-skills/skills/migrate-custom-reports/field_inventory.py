#!/usr/bin/env python3
"""Field inventory of an original Oracle report: every printed field traced to where the original computes it.

usage: field_inventory.py <program folder> [<PROG>] [--out <file.md>]

Reads what the gather put in the folder: <PROG>_rdf.xml (Oracle Reports, rwconverter XML) or <PROG>.rex (its text
export, when rwconverter fails), a BI Publisher data
template (*.xml with <dataTemplate>), the RTF layouts, and custom package bodies (*package_body.sql, *.pkb).
Writes <PROG>_field_inventory.md next to them. The Blitz expression and Proof columns are filled in during the
conversion; a printed field without a Blitz expression, and a row-control item without an implementation, is an
open defect (`custom-reports-migration` skill, "Value fidelity").
"""
import glob, html, os, re, sys
import xml.etree.ElementTree as ET

KEYWORDS = set("""select from where and or not null is in like between case when then else end nvl nvl2 decode to_char
to_number to_date trunc round substr substrb instr length upper lower trim ltrim rtrim replace sum count max min avg
sysdate distinct as dbms_xmlgen convert abs sign coalesce exists any all true false""".split())
FLOW = re.compile(r"^(for-each|for-each-group|end|if|choose|when|otherwise|call|template|import|sort|attribute|param|variable|split-by-page-break|section)\b", re.I)


def read(p):
    with open(p, "rb") as f:
        return f.read().decode("utf-8", "replace")


def strip_ns(root):
    for e in root.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]
    return root


def first_lines(text, n=3, width=160):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    return " / ".join(lines[:n])[:width]


def can_return_false(body):
    code = re.sub(r"/\*.*?\*/|--[^\n]*", " ", body or "", flags=re.S)
    return re.search(r"return\s*\(?\s*false", code, re.I) is not None


def cell(s):
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")


class Inventory:
    def __init__(self, prog):
        self.prog = prog
        self.sources = {}      # UPPER name -> (kind, definition)
        self.units = {}        # lower function name -> body
        self.printed = []      # (name, use, context) in layout order
        self.formulas = []
        self.formula_unit = {} # UPPER formula name -> lower function name
        self.dt_elements = []  # data template elements in document order
        self.row_control = []  # (kind, object, detail)
        self.queries = []      # (name, sql)
        self.package_out = []
        self.notes = []

    # ---------- Oracle Reports (rwconverter XML) ----------
    def rdf(self, path):
        try:
            root = strip_ns(ET.fromstring(read(path).encode("utf-8")))
        except ET.ParseError as e:
            self.notes.append("%s does not parse as XML (%s): read it by hand or use rex_parse.py." % (os.path.basename(path), e))
            return
        for fn in root.iter("function"):
            src = fn.find("textSource")
            self.units[(fn.get("name") or "").lower()] = src.text if src is not None and src.text else ""
        for p in list(root.iter("userParameter")) + list(root.iter("systemParameter")):
            self.sources[p.get("name", "").upper()] = ("parameter", p.get("initialValue") and "initial value %s" % p.get("initialValue") or "")
        for ds in root.iter("dataSource"):
            sel = ds.find("select")
            sql = sel.text if sel is not None and sel.text else ""
            self.queries.append((ds.get("name"), sql))
            self._groups(ds, ds.get("name"), None)
        # formulas, placeholders and summaries outside any group (report level)
        data = root.find(".//data")
        if data is not None:
            for child in data:
                self._column(child, "report level", None)
        for link in root.iter("link"):
            self.row_control.append(("link", "%s -> %s" % (link.get("parentGroup"), link.get("childQuery") or link.get("childGroup")),
                                     "a filter or empty parent group suppresses the child query"))
        for e in root.iter():
            if e.tag == "advancedLayout":
                continue
            trig = e.get("formatTrigger")
            if not trig and e.find("advancedLayout") is not None:
                trig = e.find("advancedLayout").get("formatTrigger")
            if trig:
                body = self.units.get(trig.lower(), "")
                if can_return_false(body):
                    self.row_control.append(("format trigger", "%s %s (source %s)" % (e.tag, e.get("name"), e.get("source")),
                                             "%s can return FALSE: %s" % (trig, first_lines(re.sub(r"(?is)^.*?\bbegin\b", "", body, count=1)))))
        for e in root.iter("field"):
            self.printed.append((e.get("source") or e.get("name"), "paper layout field %s" % e.get("name"), ""))
        for name, body in self.units.items():
            if name in ("beforereport", "afterpform", "afterreport", "beforepform", "betweenpages") or name.endswith("trigger") and "format" not in name:
                lex = sorted(set(re.findall(r":(\w+)\s*:=", body)))
                self.row_control.append(("trigger", name, "assigns %s" % ", ".join(lex) if lex else first_lines(body, 2)))

    def _formula(self, name, where, fn, datatype, null):
        body = self.units.get(fn, "")
        assigns = sorted(set(m.upper() for m in re.findall(r":(\w+)\s*:=", body)))
        refs = sorted(set(m.upper() for m in re.findall(r":(\w+)", body)) - set(assigns) - {name})
        into = len(re.findall(r"\binto\b", body, re.I))
        handlers = [first_lines(h, 1, 80) for h in re.findall(r"(?is)\bwhen\s+(?:others|no_data_found|too_many_rows)\b.*?(?=\bwhen\b|\bend\b)", body)]
        self.sources[name] = ("formula", "%s: %s%s%s" % (where, fn, ", " + datatype if datatype else "", ", null prints %s" % null if null else ""))
        self.formulas.append((name, where, fn, datatype, null, assigns, refs, into, handlers))
        self.formula_unit[name] = fn

    def _groups(self, node, query, group):
        for child in node:
            if child.tag == "group":
                g = child.get("name")
                self._groups(child, query, g)
            else:
                self._column(child, query, group)

    def _column(self, e, query, group):
        name = (e.get("name") or "").upper()
        where = "%s%s" % (query, " / " + group if group else "")
        if e.tag == "dataItem":
            d = e.find("dataDescriptor")
            self.sources[name] = ("query column", "%s: %s" % (where, d.get("expression") if d is not None else ""))
        elif e.tag == "formula":
            self._formula(name, where, (e.get("source") or "").lower(), e.get("datatype"), e.get("valueIfNull"))
        elif e.tag == "placeholder":
            self.sources[name] = ("placeholder", "%s, %s width %s%s" % (where, e.get("datatype"), e.get("width"), ", null prints %s" % e.get("valueIfNull") if e.get("valueIfNull") else ""))
        elif e.tag == "summary":
            self.sources[name] = ("summary", "%s: %s(%s) reset %s compute %s" % (where, e.get("function"), e.get("source"), e.get("reset"), e.get("compute")))
        elif e.tag == "filter":
            if e.get("type") == "plsql":
                body = self.units.get((e.get("plsqlFilter") or "").lower(), "")
                self.row_control.append(("group filter", group, "%s: %s" % (e.get("plsqlFilter"), first_lines(re.sub(r"(?is)^.*?\bbegin\b", "", body, count=1)))))
            else:
                self.row_control.append(("group filter", group, "%s %s records" % (e.get("type"), e.get("numberOfRecords"))))

    # ---------- Oracle Reports text export (.rex), when rwconverter fails ----------
    def rex(self, path):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import rex_parse
        recs = rex_parse.parse(path)
        by_id = {r.get("ITEMID"): r for r in recs if r.get("ITEMID")}
        groups = {r.get("ITEMID"): r for r in recs if r["_type"] == "SRW2_GROUP"}
        queries = {r.get("ITEMID"): r.get("NAME") for r in recs if r["_type"] == "SRW2_QUERY"}
        owner = {}
        for r in recs:
            if r["_type"] == "SRW2_QUERY":
                self.queries.append((r.get("NAME"), r.get("QUERYLFID") or ""))
            elif r["_type"] == "TOOL_PLSQL":
                self.units[(r.get("NAME") or "").lower()] = r.get("PLSLFID_ST") or ""
                owner.setdefault(r.get("OBJECT_ID"), []).append(r)
        for r in recs:
            if r["_type"] != "SRW2_COLUMN":
                continue
            g = groups.get(r.get("GROUP_ID"), {})
            where = "%s / %s" % (queries.get(g.get("QUERY_ID"), "report level"), g.get("NAME")) if g else "report level"
            name = (r.get("NAME") or "").upper()
            null = r.get("NULL_VALUE") if r.get("NULL_VALUE") not in (None, "NULLP") else None
            units = [u for u in owner.get(r.get("ITEMID"), []) if u.get("TYPE") == "4"]
            if units:
                self._formula(name, where, units[0].get("NAME").lower(), "", null)
            else:
                self.sources.setdefault(name, ("column", "%s (query column, summary, placeholder or parameter: see the .rex)%s" % (where, ", null prints %s" % null if null else "")))
        for r in recs:
            if r["_type"] == "TOOL_PLSQL" and r.get("TYPE") != "4":
                o = by_id.get(r.get("OBJECT_ID"), {})
                body = r.get("PLSLFID_ST") or ""
                if o.get("_type") in ("SRW2_FRAME", "SRW2_FIELD", "SRW2_BOILERPLATE"):
                    if can_return_false(body):
                        self.row_control.append(("format trigger", "%s %s" % (o["_type"][5:].lower(), o.get("NAME")),
                                                 "%s can return FALSE: %s" % (r.get("NAME"), first_lines(re.sub(r"(?is)^.*?\bbegin\b", "", body, count=1)))))
                elif o.get("_type") == "SRW2_GROUP":
                    self.row_control.append(("group filter", o.get("NAME"), "%s: %s" % (r.get("NAME"), first_lines(re.sub(r"(?is)^.*?\bbegin\b", "", body, count=1)))))
                elif r.get("TYPE") in ("7", "8", "9", "10"):
                    lex = sorted(set(re.findall(r":(\w+)\s*:=", body)))
                    self.row_control.append(("trigger", r.get("NAME"), "assigns %s" % ", ".join(lex) if lex else first_lines(body, 2)))
            elif r["_type"] == "SRW2_LINK":
                p, c = by_id.get(r.get("PARENT_ID"), {}), by_id.get(r.get("CHILD_ID"), {})
                self.row_control.append(("link", "%s -> %s" % (p.get("NAME"), c.get("NAME")), "a filter or empty parent group suppresses the child"))
            elif r["_type"] == "SRW2_FIELD":
                src = by_id.get(r.get("SOURCE_ID"), {})
                if src.get("NAME"):
                    self.printed.append((src.get("NAME"), "paper layout field %s" % r.get("NAME"), ""))

    # ---------- BI Publisher data template ----------
    def data_template(self, path):
        try:
            root = strip_ns(ET.fromstring(read(path).encode("utf-8")))
        except ET.ParseError as e:
            self.notes.append("%s does not parse as XML (%s)." % (os.path.basename(path), e))
            return
        if root.get("defaultPackage"):
            self.notes.append("Data template %s uses default package %s: read its triggers and functions." % (os.path.basename(path), root.get("defaultPackage")))
        for p in root.iter("parameter"):
            self.sources[(p.get("name") or "").upper()] = ("parameter", "")
        for q in root.iter("sqlStatement"):
            self.queries.append((q.get("name"), q.text or ""))
        for t in root.iter("dataTrigger"):
            self.row_control.append(("data trigger", t.get("name"), t.get("source")))
        for g in root.iter("group"):
            if g.get("groupFilter"):
                self.row_control.append(("group filter", g.get("name"), g.get("groupFilter")))
            for el in g.findall("element"):
                n = (el.get("name") or "").strip().upper()
                kind = "summary" if el.get("function") else "query column"
                self.sources[n] = (kind, "%s / %s: %s%s" % (g.get("source"), g.get("name"), (el.get("value") or "").strip(),
                                   " %s()" % el.get("function") if el.get("function") else ""))
                if g.get("name") != "G_PARAMETERS":
                    self.dt_elements.append(n)
        for lk in root.iter("link"):
            self.row_control.append(("link", "%s -> %s" % (lk.get("parentQuery"), lk.get("childQuery")), lk.get("condition") or ""))

    # ---------- RTF layout ----------
    def rtf(self, path):
        text = read(path)
        text = re.sub(r"\\'[0-9a-fA-F]{2}", "", text)
        text = re.sub(r"\\(rquote|lquote)\s?", "'", text)
        text = re.sub(r"\\(rdblquote|ldblquote)\s?", '"', text)
        text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
        text = re.sub(r"[{}\r\n]", "", text)
        seen = set(n for n, _, _ in self.printed)
        for tok in re.findall(r"<\?(.{1,400}?)\?>", text):
            tok = tok.strip()
            names = [n.upper() for n in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", tok) if n.lower() not in KEYWORDS]
            if FLOW.match(tok) or re.match(r"^(xdoxslt|xdofx|xdoxliff):", tok, re.I) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tok):
                known = [n for n in names if n in self.sources]
                if re.match(r"^(if|choose|when)\b", tok, re.I) or "position()" in tok:
                    self.row_control.append(("layout condition", os.path.basename(path), tok[:200]))
                elif re.match(r"^for-each", tok, re.I):
                    self.row_control.append(("layout loop", os.path.basename(path), tok[:200]))
                elif known:
                    for n in known:
                        if n not in seen:
                            seen.add(n)
                            self.printed.append((n, "layout expression", tok[:120]))
                continue
            n = tok.upper()
            if n not in seen:
                seen.add(n)
                self.printed.append((n, "layout field", os.path.basename(path)))

    # ---------- PL/SQL package (execution method I, or a data template's package) ----------
    def package(self, path, entry=None):
        """entry: the executable's procedure name; output is then read from that procedure only."""
        text = read(path)
        lines = text.splitlines()
        lo, hi = 0, len(text)
        if entry:
            # the definition, not a forward declaration: 'is' or 'as' comes before the first semicolon
            starts = [m.start() for m in re.finditer(r"(?im)^\s*procedure\s+%s\b" % re.escape(entry), text)
                      if re.search(r"(?i)\b(is|as)\b", text[m.end():text.find(";", m.end())])]
            if not starts:
                return
            lo = starts[-1]
            end = re.compile(r"(?im)^\s*end\s+%s\s*;" % re.escape(entry)).search(text, lo)
            nxt = re.compile(r"(?im)^\s*(procedure|function)\s+\w+").search(text, lo + 10)
            hi = end.end() if end else (nxt.start() if nxt else len(text))
            self.notes.append("Output read from procedure %s of %s (lines %d-%d); procedures it calls that print are not followed: read them by hand." % (
                entry, os.path.basename(path), text.count("\n", 0, lo) + 1, text.count("\n", 0, hi) + 1))
        literal_cols = {}
        for m in re.finditer(r"(?is)(?:select|,)\s*(null|0|-?\d+(?:\.\d+)?|'[^']*')\s+(?:as\s+)?([a-z_][a-z0-9_$#]*)\s*(?=,|\bfrom\b)", text):
            literal_cols.setdefault(m.group(2).lower(), m.group(1))
        inserts = sorted(set(m.lower() for m in re.findall(r"(?i)\binsert\s+into\s+([a-z0-9_$#.]+)", text[lo:hi])))
        if inserts:
            self.notes.append("%s inserts into %s: the rows the layout prints may be written by code, not selected." % (os.path.basename(path), ", ".join(inserts)))

        def computed_at(expr):
            where = []
            for x in [x for x in re.findall(r"[A-Za-z_][A-Za-z0-9_$#]*(?:\.[A-Za-z_][A-Za-z0-9_$#]*)?", re.sub(r"'[^']*'", "", expr)) if x.lower() not in KEYWORDS]:
                base = x.split(".")[-1].lower()
                if "." in x:
                    if base in literal_cols:
                        where.append("%s is the cursor literal %s: filled by loop code?" % (x, literal_cols[base]))
                    continue
                hits = [str(j) for j, l in enumerate(lines, 1) if re.search(r"(?i)\b%s\s*:=" % re.escape(x), l) or re.search(r"(?i)\binto\b.*\b%s\b" % re.escape(x), l)]
                if hits:
                    where.append("%s assigned at line %s" % (x, ", ".join(hits[:12]) + (" ..." if len(hits) > 12 else "")))
            return "; ".join(where)

        def add(name, line, expr):
            self.package_out.append((name, line, expr.strip()[:120], computed_at(expr)))
            self.sources.setdefault(name.upper(), ("package output", "%s line %d: %s" % (os.path.basename(path), line, expr.strip()[:100])))

        # XML elements: '<TAG>'||expr||'</TAG>'
        for m in re.finditer(r"(?i)'\s*<(\w+)>\s*'\s*\|\|\s*(.+?)\s*\|\|\s*'\s*</\1>\s*'", text[lo:hi]):
            add(m.group(1).upper(), text.count("\n", 0, lo + m.start()) + 1, m.group(2))
        # XML elements written through a helper: <helper>('TAG',expr), where the helper builds '<'||tag||'>'
        helpers = []
        for m in re.finditer(r"(?im)^\s*procedure\s+(\w+)\s*\(", text):
            body_end = re.compile(r"(?im)^\s*end\s+%s\s*;" % re.escape(m.group(1))).search(text, m.end())
            if body_end and re.search(r"'<'\s*\|\|", text[m.end():body_end.start()]):
                helpers.append(m.group(1))
        for h in set(helpers):
            for m in re.finditer(r"(?i)\b%s\s*\(\s*'(\w+)'\s*,\s*" % re.escape(h), text[lo:hi]):
                start, depth, i = lo + m.end(), 1, lo + m.end()
                while i < hi and depth:
                    depth += {"(": 1, ")": -1}.get(text[i], 0)
                    i += 1
                add(m.group(1).upper(), text.count("\n", 0, lo + m.start()) + 1, text[start:i - 1])
        # delimited text lines: a heading line of literals, then data lines of values joined with '|', ',' or a tab
        headings = []
        for m in re.finditer(r"(?i)\b(?:fnd_file\.put_line\s*\(\s*fnd_file\.output\s*,|fnd_file\.put\s*\(\s*fnd_file\.output\s*,|utl_file\.put_line\s*\(\s*\w+\s*,|utl_file\.put\s*\(\s*\w+\s*,)", text[lo:hi]):
            start = lo + m.end()
            expr, depth, q, i = None, 1, False, start
            while i < hi:
                c = text[i]
                if q:
                    if c == "'":
                        if text[i + 1:i + 2] == "'":
                            i += 1
                        else:
                            q = False
                elif c == "'":
                    q = True
                elif c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        expr = text[start:i]
                        break
                i += 1
            if expr is None or re.search(r"(?i)'\s*<\w+>", expr):
                continue
            pieces, cur, depth, q = [], "", 0, False
            j = 0
            while j < len(expr):
                c = expr[j]
                if q:
                    cur += c
                    if c == "'":
                        if expr[j + 1:j + 2] == "'":
                            cur += "'"
                            j += 1
                        else:
                            q = False
                elif c == "'":
                    q = True
                    cur += c
                elif c == "(":
                    depth += 1
                    cur += c
                elif c == ")":
                    depth -= 1
                    cur += c
                elif expr.startswith("||", j) and depth == 0:
                    pieces.append(cur.strip())
                    cur = ""
                    j += 1
                else:
                    cur += c
                j += 1
            pieces.append(cur.strip())
            delim = lambda p: re.fullmatch(r"(?i)chr\s*\(\s*(9|44|124)\s*\)|'[\s|,~;^\"\t]*'", p) is not None
            literal = lambda p: re.fullmatch(r"'(?:[^']|'')*'", p) is not None
            values = [p for p in pieces if p and not delim(p)]
            line = text.count("\n", 0, start) + 1
            if values and all(literal(p) for p in values):
                heads = []
                for p in values:
                    heads += [h.strip() for h in re.split(r"[|\t]|\\t", p[1:-1].replace("''", "'")) if h.strip()]
                if len(heads) > 1:
                    headings = heads
                continue
            if len(values) < 2:
                continue
            for k, v in enumerate(values):
                add(headings[k] if len(headings) == len(values) else "%s value %d" % (os.path.basename(path).split(".")[1] if "." in os.path.basename(path) else "output", k + 1), line, v)

    # ---------- report ----------
    def write(self, out):
        printed = list(self.printed or [(t, "package output", "") for t, _, _, _ in self.package_out])
        if not printed and self.dt_elements:
            self.notes.append("No layout file in the folder: the printed fields below are the data template's elements. "
                              "Take the printed set, order and headings from the customer's layout or an ERP output.")
            printed = [(n, "data template element", "") for n in self.dt_elements]
        # a printed formula that concatenates other columns into a text line prints each of them
        seen = set(n.upper() for n, _, _ in printed)
        for n, _, _ in list(printed):
            body = self.units.get(self.formula_unit.get(n.upper(), ""), "")
            if body.count("||") >= 3:
                for ref in re.findall(r":(\w+)", body):
                    if ref.upper() not in seen and ref.upper() in self.sources:
                        seen.add(ref.upper())
                        printed.append((ref, "printed inside %s" % n, ""))
        w = []
        a = w.append
        a("# Field inventory: %s" % self.prog)
        a("")
        a("Every printed field, and everything that decides which rows print, traced to where the original computes it. Fill the "
          "Blitz expression and Proof columns during the conversion; an empty Blitz expression or implementation is an open defect.")
        a("")
        for n in self.notes:
            a("- " + n)
        if self.notes:
            a("")
        a("## 1. Printed fields (%d)" % len(printed))
        a("")
        a("| # | Field | Where it is used | Source in the original | Blitz expression | Proof |")
        a("|---|---|---|---|---|---|")
        for i, (n, use, ctx) in enumerate(printed, 1):
            kind, d = self.sources.get(n.upper(), ("UNRESOLVED", "not found in the data model: read the source"))
            a("| %d | %s | %s | %s: %s | | |" % (i, cell(n), cell(use if not ctx else "%s (%s)" % (use, ctx)), kind, cell(d)))
        a("")
        a("## 2. Formula columns (%d)" % len(self.formulas))
        a("")
        a("Each needs its SQL equivalent, including what its exception handlers print when a lookup finds no row or several, "
          "and every placeholder it assigns.")
        a("")
        a("| Formula | Group | Function | Returns | Null prints | Assigns | Reads | select into | Handlers | Blitz expression |")
        a("|---|---|---|---|---|---|---|---|---|---|")
        for f in self.formulas:
            a("| %s | %s | %s | %s | %s | %s | %s | %d | %s | |" % (cell(f[0]), cell(f[1]), cell(f[2]), cell(f[3]), cell(f[4]),
              cell(", ".join(f[5])), cell(", ".join(f[6])[:200]), f[7], cell("; ".join(f[8])[:200])))
        a("")
        a("## 3. Row and section control (%d)" % len(self.row_control))
        a("")
        a("Group filters, links, format triggers that can return FALSE, layout conditions and loops, and triggers that build "
          "lexicals decide which rows and sections print. Each needs an implementation or a stated reason why it never fires.")
        a("")
        a("| Kind | Object | Detail | Implementation |")
        a("|---|---|---|---|")
        for k, o, d in self.row_control:
            a("| %s | %s | %s | |" % (cell(k), cell(o), cell(d)))
        a("")
        a("## 4. Queries (%d)" % len(self.queries))
        a("")
        a("A `union` de-duplicates over its whole select list, ids and rowids included: keep the original's operator and key. "
          "Lexicals are filled by the triggers listed above.")
        a("")
        a("| Query | union | union all | order by | Lexicals |")
        a("|---|---|---|---|---|")
        for n, sql in self.queries:
            s = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql or "", flags=re.S)
            s = re.sub(r"'[^']*'", "''", s)
            a("| %s | %d | %d | %s | %s |" % (cell(n), len(re.findall(r"(?i)\bunion\b(?!\s+all\b)", s)), len(re.findall(r"(?i)\bunion\s+all\b", s)),
              "yes" if re.search(r"(?i)\border\s+by\b", s) else "no", cell(", ".join(sorted(set(re.findall(r"&(\w+)", s)))))))
        if self.package_out:
            a("")
            a("## 5. Package output elements (%d)" % len(self.package_out))
            a("")
            a("Values the program prints from variables are computed by its loop code, not by the cursor: replicate those "
              "assignments. A cursor literal (`0 basic`, `null source`) is a placeholder the loop fills.")
            a("")
            a("| Element | Line | Expression | Computed at | Blitz expression |")
            a("|---|---|---|---|---|")
            for t, i, e, wh in self.package_out:
                a("| %s | %d | %s | %s | |" % (cell(t), i, cell(e), cell(wh)))
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(w) + "\n")
        unresolved = sum(1 for n, _, _ in printed if n.upper() not in self.sources)
        print("%s: %d printed fields (%d unresolved), %d formulas, %d row-control items, %d queries, %d package output elements -> %s" % (
            self.prog, len(printed), unresolved, len(self.formulas), len(self.row_control), len(self.queries), len(self.package_out), out))


def main():
    args = sys.argv[1:]
    out = None
    if "--out" in args:
        i = args.index("--out")
        out = args[i + 1]
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    folder = args[0]
    prog = args[1] if len(args) > 1 else os.path.basename(os.path.normpath(folder))
    inv = Inventory(prog)
    # the RDF is named after the executable, which can differ from the program short name
    rdf = next(iter([os.path.join(folder, prog + "_rdf.xml")] if os.path.exists(os.path.join(folder, prog + "_rdf.xml")) else sorted(glob.glob(os.path.join(folder, "*_rdf.xml")))), None)
    rex = next(iter(sorted(glob.glob(os.path.join(folder, "*.rex")))), None)
    if rdf:
        inv.rdf(rdf)
    elif rex:
        inv.rex(rex)
    elif glob.glob(os.path.join(folder, "*.rdf")):
        inv.notes.append("No _rdf.xml or .rex: rwconverter failed. Ask the customer for the .rex text export (Reports Builder: File > Convert) and put it in this folder.")
    for x in glob.glob(os.path.join(folder, "*.xml")):
        if x != rdf and "<dataTemplate" in read(x)[:5000]:
            inv.data_template(x)
    # a PL/SQL program's output comes from its executable: PKG.PROCEDURE, or a standalone procedure
    pkg = proc = None
    ldt = os.path.join(folder, prog + ".ldt")
    if os.path.exists(ldt):
        m = re.search(r'(?s)BEGIN EXECUTABLE .*?EXECUTION_METHOD_CODE = "(\w)".*?EXECUTION_FILE_NAME = "([^"]+)"', read(ldt))
        if m and m.group(1) == "I":
            parts = m.group(2).split(".")
            pkg, proc = (parts[-2].upper(), parts[-1]) if len(parts) > 1 else (None, parts[-1])
    code = sorted(glob.glob(os.path.join(folder, "*package_body.sql")) + glob.glob(os.path.join(folder, "*.pkb")) + glob.glob(os.path.join(folder, "*procedure.sql")))
    entry_files = [p for p in code if pkg and ".%s." % pkg in os.path.basename(p).upper() or not pkg and proc and ".%s." % proc.upper() in os.path.basename(p).upper()]
    for p in entry_files or code:
        inv.package(p, proc if pkg and p in entry_files else None)
    for r in sorted(glob.glob(os.path.join(folder, "*.rtf"))):
        inv.rtf(r)
    inv.write(out or os.path.join(folder, prog + "_field_inventory.md"))


if __name__ == "__main__":
    main()
