"""Pre-publish checks for a performance review. Run from the working folder:

    python verify_deliverables.py <report.html> [more files or folders...]

Fails loudly on: a sql_id cited in the review html that is not in awr.json or sga.json,
control characters, a UTF-8 BOM, LF-only .pkb, a .diff file, a section reference that
does not resolve, a second numbering scheme ("Finding N"), and words an expert
reader should not have to look up.
"""
import glob
import html
import json
import os
import re
import sys

BANNED = ["memois", "orthogonal", "leverag", "utilis", "holistic", "paradigm", "wannabe",
          "belt-and-braces", "in order to", "it is worth noting", "needless to say"]

ids = set()
for f in ("awr.json", "sga.json"):
    if os.path.exists(f):
        for r in json.load(open(f, encoding="utf-8")):
            if r.get("Sql Id"):
                ids.add(r["Sql Id"])

# sql_ids that come from other extracts (plan history, ASH) rather than the two summaries
if os.path.exists("known_ids.txt"):
    ids.update(l.strip() for l in open("known_ids.txt", encoding="utf-8") if l.strip())

SQLID = re.compile(r"(?<![0-9a-z])(?=[a-z0-9]{13}(?![0-9a-z]))(?=[a-z0-9]*[0-9])(?=[a-z0-9]*[a-z])[a-z0-9]{13}")

files = []
for a in sys.argv[1:]:
    files += [a] if os.path.isfile(a) else glob.glob(os.path.join(a, "**", "*"), recursive=True)

problems = 0
for p in files:
    if os.path.isdir(p) or p.endswith((".xlsx", ".json", ".py")):
        continue
    b = open(p, "rb").read()
    name = os.path.basename(p)
    if b.startswith(b"\xef\xbb\xbf"):
        print("BOM         ", name); problems += 1
    if [c for c in set(b) if c < 9 or 11 <= c <= 12 or 14 <= c <= 31]:
        print("control char", name); problems += 1
    if name.endswith(".diff"):
        print("diff file   ", name); problems += 1
    if name.endswith(".pkb") and b.count(b"\r\n") * 2 < b.count(b"\n"):
        print("LF only     ", name); problems += 1
    text = b.decode("utf-8", "replace")
    plain = html.unescape(re.sub("<[^>]+>", " ", text))
    for m in SQLID.finditer(plain) if name.endswith(".html") else ():
        t = m.group(0)
        if ids and t not in ids and not t.isalpha():
            print("unknown id  ", name, t); problems += 1
    # banned words apply to our prose, not to the customer's own code
    for w in BANNED if not name.endswith((".pkb", ".pks", ".sql")) else ():
        if w in plain.lower():
            print("banned word ", name, repr(w)); problems += 1
    if name.endswith(".html"):
        secs = {int(m.group(1)) for m in re.finditer(r"<h2[^>]*>(\d+)\.", text)}
        body = re.sub(r"<h2[^>]*>.*?</h2>", "", text, flags=re.S)
        for m in re.finditer(r"\b[Ss]ections? (\d+)\b", html.unescape(re.sub("<[^>]+>", " ", body))):
            if int(m.group(1)) not in secs:
                print("dangling ref", name, m.group(0)); problems += 1
        if re.search(r"\b[Ff]inding \d+", plain):
            print("second numbering scheme (Finding N)", name); problems += 1
        if re.search(r"<pre>[^<]*\n\s*\n", text):
            print("blank lines inside <pre>", name); problems += 1

print("OK" if not problems else f"{problems} problems")
sys.exit(1 if problems else 0)
