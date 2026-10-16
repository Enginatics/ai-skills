#!/usr/bin/env python
"""Offline assignments gate for the custom-reports migration (Phase 2).

Asserts that the <ASSIGNMENTS> block of each built report XML reproduces the gathered
<PROG>_assignments.xml EXACTLY - every request group carried, each with its OWN application
short name, and the level code normalised for the target instance.

Needs NO database. That is the point: on a conversion instance the customer's request groups
do not exist, so the import legitimately reports 0 assignments and can tell you nothing about
whether the XML was right. A zero there is UNVERIFIABLE, not PASSED - accepting it lets a
defect ship (a few of the groups carried per report, all stamped with the customer's custom
application instead of JA / SQLAP / AR / JE / SQLGL).

LEVEL CODE
  Builds before 21-Jun-2026 use single letters; from that build on the import
  decodes only the full words and SILENTLY SKIPS anything else. Gathered packages produced before
  the converter fix carry 'G'. Legacy mapping:
      S->Site  A->Application  G->Request Group  R->Responsibility
      U->User  F->Form         D->Report         (Function has no legacy letter)

USAGE
  python verify_assignments.py --gather <CONV_folder> --built <folder-with-built-XMLs> \
                               --map map.json [--level "Request Group"]

  map.json maps each built XML file to its source program(s). The deliverable is ONE category file,
  so the normal shape maps that file to {"<Blitz report name>": "<PROG>", ...} and the gate checks each
  report's rows separately; a plain string value (one XML per program) is still accepted:
      {"reports_Custom_Reports_ABC_with_assignments_v01.xml": {"ABC Item Extract": "XX_ITEM_EXTRACT",
                                                              "ABC Asset Detail": "XX_ASSET_DETAIL"}}

Exit code 0 = gate passed, 1 = gate failed.
"""
import argparse
import html
import json
import os
import re
import sys

LEGACY = {'S': 'Site', 'A': 'Application', 'G': 'Request Group', 'R': 'Responsibility',
          'U': 'User', 'F': 'Form', 'D': 'Report'}


def rows(path, report_name=None):
    """(level_value, application_short_name, assignment_level) per ASSIGNMENTS_ROW, optionally of one report"""
    x = open(path, encoding='utf-8').read()
    out = []
    for m in re.finditer(r'<ASSIGNMENTS_ROW>(.*?)</ASSIGNMENTS_ROW>', x, re.S):
        r = m.group(1)
        rn = re.search(r'<REPORT_NAME>(.*?)</REPORT_NAME>', r, re.S)
        if report_name is not None and (not rn or html.unescape(rn.group(1)) != report_name):
            continue
        lv = re.search(r'<LEVEL_VALUE>(.*?)</LEVEL_VALUE>', r, re.S)
        ap = re.search(r'<APPLICATION_SHORT_NAME>(.*?)</APPLICATION_SHORT_NAME>', r, re.S)
        al = re.search(r'<ASSIGNMENT_LEVEL>(.*?)</ASSIGNMENT_LEVEL>', r, re.S)
        out.append((html.unescape(lv.group(1)) if lv else '',
                    ap.group(1) if ap else '',
                    al.group(1) if al else ''))
    return out


def normalise(level):
    return LEGACY.get(level, level)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--gather', required=True, help='extracted CONV_<ABBR>_... folder')
    p.add_argument('--built', required=True, help='folder holding the built report XMLs')
    p.add_argument('--map', required=True, help='JSON: {"<built xml>": "<PROG>"}')
    p.add_argument('--level', default='Request Group',
                   help='level code the TARGET instance expects (default: full words)')
    a = p.parse_args()

    mapping = json.load(open(a.map, encoding='utf-8'))
    fail = 0
    checks = []
    for xml in sorted(mapping):
        if isinstance(mapping[xml], dict):
            checks += [(xml, name, prog) for name, prog in sorted(mapping[xml].items())]
        else:
            checks.append((xml, None, mapping[xml]))
    for xml, name, prog in checks:
        label = (name or xml)[:50]
        bpath = os.path.join(a.built, xml)
        gpath = os.path.join(a.gather, prog, prog + '_assignments.xml')
        if not os.path.exists(gpath):
            print('%-52s NO GATHERED FILE (%s)' % (label, gpath))
            fail += 1
            continue
        built, gathered = rows(bpath, name), rows(gpath)
        b = {(v, ap) for v, ap, _ in built}
        g = {(v, ap) for v, ap, _ in gathered}
        bad_level = {l for _, _, l in built} - {a.level}
        ok = not (g - b) and not (b - g) and not bad_level
        print('%-52s %2d/%2d  %s' % (label, len(built), len(gathered), 'OK' if ok else 'FAIL'))
        for v, ap in sorted(g - b):
            print('      MISSING from built XML : %s @ %s' % (v, ap)); fail += 1
        for v, ap in sorted(b - g):
            print('      NOT IN gathered file   : %s @ %s' % (v, ap)); fail += 1
        for l in sorted(bad_level):
            hint = ' (legacy for %s - normalise it)' % normalise(l) if l in LEGACY else ''
            print('      WRONG level code       : %s, expected %s%s' % (l, a.level, hint)); fail += 1

    print()
    print('ASSIGNMENTS GATE PASSED' if not fail else 'ASSIGNMENTS GATE FAILED (%d problems)' % fail)
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
