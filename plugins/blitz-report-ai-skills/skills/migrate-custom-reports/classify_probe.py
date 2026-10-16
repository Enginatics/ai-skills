#!/usr/bin/env python
"""Classification probe for the custom-reports migration (Phase 2).

Produces the evidence needed to classify a gathered custom report as Outcome 1 / 2 / 3.
Run this BEFORE deciding the outcome and paste its output into the engagement notes.
A column-name comparison is NOT a classification - this probe compares DATA SOURCES,
which is what actually decides whether a shipped Blitz Report can produce the rows.

Example: a custom GL detail report looked like a two-column enhancement of the shipped
"GL Account Analysis" from column-name overlap alone. The shipped report has ZERO India
Localization references and 2 union branches; the custom report had 8 branches, 4 JAI tables
and 25 calls to a customer package. It was Outcome 3.

USAGE
  # 1. dump the candidate shipped report's SQL from the conversion instance FIRST:
  #    (base table, NOT xxen_reports_v - the view truncates the CLOB at 32764 bytes)
  #      select xr.sql_text from xxen_reports xr, xxen_reports_v v
  #      where xr.report_id=v.report_id and v.report_name='<shipped report>';
  #    save it as shipped.sql
  #
  # 2. python classify_probe.py --custom _extract/<PROG>_datamodel_1.sql \
  #                             --shipped shipped.sql \
  #                             --prefixes XX,YY
  #
  # --prefixes: ALL customer object prefixes, comma separated. Do not assume the one in
  #   manifest.txt is complete - the gather itself only scans for that one, which is how
  #   dependencies get missed (see `custom-reports-migration` skill "Gathering - known gaps").

VERDICT RULE (deterministic - do not override with judgement):
  * any localization object (JAI_/JA_IN_) present in custom but absent in shipped  -> OUTCOME 3
  * any customer-owned object (matching a prefix) referenced by the custom SQL     -> OUTCOME 3
  * custom has materially more union branches than shipped                         -> OUTCOME 3 (investigate)
  * otherwise                                                                      -> Outcome 1/2 candidate,
                                                                                      continue with the column diff
"""
import argparse
import os
import re
import sys

ORACLE_STD = re.compile(
    r'^(ap|ar|gl|po|inv|mtl|wip|bom|fa|pa|pn|ce|xla|hr|hz|per|fnd|ra|rcv|oe|ont|wsh|qp|cst|msc|'
    r'jtf|okc|iby|ego|eam|gmd|gme|gmf|gmi|gmp|opm|cs|csi|cse|zx|xle|xdo|ak|alr|icx|jg|qa|bne|'
    r'ben|pay|ota|pqh|pqp|ssp|pjm|pji|pjc|pn|igi|igc|igs|dual)_',
    re.I)

FROM_RE = re.compile(
    r'(?:\bfrom\b|\bjoin\b|,)\s*(?:([a-z][a-z0-9_$#]{0,60})\s*\.\s*)?([a-z][a-z0-9_$#]{2,60})\s*(?=[\s,);]|$)', re.I)  # ';' - a table may be the last token of the statement
PKG_RE = re.compile(r'(?<![.\w])([a-z][a-z0-9_$#]{2,60})\s*\.\s*[a-z][a-z0-9_$#]*\s*\(', re.I)
FUNC_RE = re.compile(r'(?<![.\w])([a-z][a-z0-9_$#]{2,60})\s*\(', re.I)  # standalone function call, e.g. xx_item_attribute(
SQL_KEYWORDS = {
    'select', 'where', 'and', 'or', 'group', 'order', 'by', 'having', 'union', 'all',
    'from', 'join', 'on', 'as', 'case', 'when', 'then', 'else', 'end', 'null', 'not',
    'in', 'exists', 'is', 'dual', 'distinct', 'left', 'right', 'outer', 'inner', 'full',
    'connect', 'start', 'with', 'over', 'partition', 'rownum', 'decode', 'nvl', 'trunc',
    'to_char', 'to_date', 'to_number', 'substr', 'instr', 'sum', 'count', 'max', 'min',
    'avg', 'round', 'lower', 'upper', 'sysdate', 'userenv', 'set', 'values', 'into',
}


def strip_noise(sql):
    """remove block/line comments and string literals so we only scan real identifiers"""
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.S)
    sql = re.sub(r'--[^\n]*', ' ', sql)
    sql = re.sub(r"'(?:''|[^'])*'", " '' ", sql)
    return sql


def objects(sql, prefixes):
    def startswith_prefix(name):
        return any(name.startswith(p.lower()) for p in prefixes)

    # dynamic SQL built in string literals (a BeforeReport lexical) can call customer packages
    literals = ' '.join(re.findall(r"'((?:''|[^'])*)'", re.sub(r'--[^\n]*', ' ', re.sub(r'/\*.*?\*/', ' ', sql, flags=re.S))))
    found = {m.group(1).lower() for r in (PKG_RE, FUNC_RE) for m in r.finditer(literals) if startswith_prefix(m.group(1).lower())}
    sql = strip_noise(sql)

    for m in FROM_RE.finditer(sql):
        schema, obj = (m.group(1) or '').lower(), m.group(2).lower()
        # a schema-qualified table hides a customer object when only the SCHEMA carries
        # the prefix (xxc.some_table); keep the qualified name so it is not read as standard
        if schema and startswith_prefix(schema) and not startswith_prefix(obj):
            found.add('%s.%s' % (schema, obj))
        else:
            found.add(obj)
    for m in PKG_RE.finditer(sql):
        found.add(m.group(1).lower())
    for m in FUNC_RE.finditer(sql):
        if any(m.group(1).lower().startswith(p.lower()) for p in prefixes):
            found.add(m.group(1).lower())
    found = {f for f in found if f not in SQL_KEYWORDS and not f.isdigit()}

    loc, cust, std, other = set(), set(), set(), set()
    for f in found:
        if f.startswith('jai_') or f.startswith('ja_in') or f.startswith('jai'):
            loc.add(f)
        elif any(f.startswith(p.lower()) for p in prefixes):
            cust.add(f)
        elif ORACLE_STD.match(f):
            std.add(f)
        else:
            other.add(f)
    return loc, cust, std, other


def branches(sql):
    return len(re.findall(r'(?mi)^\s*union\s+all\s*$', strip_noise(sql))) + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--custom', required=True, help='the gathered custom report SQL')
    ap.add_argument('--shipped', help='the candidate shipped Blitz report SQL (from xxen_reports base table)')
    ap.add_argument('--prefixes', default='XX', help='comma separated customer object prefixes')
    a = ap.parse_args()

    prefixes = [p.strip() for p in a.prefixes.split(',') if p.strip()]
    csql = open(a.custom, encoding='utf-8', errors='replace').read()
    cloc, ccust, cstd, cother = objects(csql, prefixes)
    cbr = branches(csql)

    print('=' * 78)
    print('CLASSIFICATION PROBE')
    print('=' * 78)
    print('custom report : %s' % os.path.basename(a.custom))
    print('  union branches            : %d' % cbr)
    print('  localization objects (%d)  : %s' % (len(cloc), ', '.join(sorted(cloc)) or '-'))
    print('  customer objects     (%d)  : %s' % (len(ccust), ', '.join(sorted(ccust)) or '-'))
    print('  standard EBS objects (%d)' % len(cstd))
    if cother:
        print('  UNCLASSIFIED         (%d)  : %s' % (len(cother), ', '.join(sorted(cother))))
        print('     ^ check these by hand - an unrecognised prefix hides customer objects')

    sloc = scust = sstd = set()
    sbr = 0
    if a.shipped:
        ssql = open(a.shipped, encoding='utf-8', errors='replace').read()
        sloc, scust, sstd, _ = objects(ssql, prefixes)
        sbr = branches(ssql)
        print()
        print('shipped report: %s' % os.path.basename(a.shipped))
        print('  union branches            : %d' % sbr)
        print('  localization objects (%d)  : %s' % (len(sloc), ', '.join(sorted(sloc)) or '-'))
        print('  standard EBS objects (%d)' % len(sstd))

    missing_loc = cloc - sloc
    print()
    print('-' * 78)
    print('VERDICT')
    print('-' * 78)
    reasons = []
    if missing_loc:
        reasons.append('custom uses %d localization object(s) the shipped report does not: %s'
                       % (len(missing_loc), ', '.join(sorted(missing_loc))))
    if ccust:
        reasons.append('custom depends on %d customer-owned object(s): %s'
                       % (len(ccust), ', '.join(sorted(ccust))))
    if a.shipped and cbr > sbr:
        reasons.append('custom has %d union branches vs %d in the shipped report' % (cbr, sbr))

    if reasons:
        print('  OUTCOME 3 - build a new custom report')
        for r in reasons:
            print('    - %s' % r)
        if ccust:
            print()
            print('  ACTION: confirm every customer object above has a gathered .sql dependency')
            print('          file. If not, request the source from the customer BEFORE building')
            print('          (DBA Text Search report) - the gather only scans the ONE prefix in')
            print('          manifest.txt, so objects under any other naming are silently missing.')
        rc = 3
    else:
        print('  Outcome 1/2 CANDIDATE - no localization or customer-object blockers found.')
        print('  Now do the column diff to decide between 1 (complete map) and 2 (enhance),')
        print('  comparing against ALL templates of the shipped report, not just one.')
        rc = 0
    print()
    return rc


if __name__ == '__main__':
    sys.exit(main())
