"""Turn gathered WebADI integrator definitions into Form Analysis Documents for the upload-builder skill.

usage: python webadi_fad.py <gathered folder | integrator folder | <INTEGRATOR>_integrator.ldt> [--content <folder of shipped upload XMLs>] [--extensions <folder of upload packages>]

Writes FAD_<INTEGRATOR>.md next to each integrator definition that uploads data, and webadi_inventory.md
(one row per integrator: what it is, what it calls, what is missing) into the folder given.
"""
import argparse
import os
import pathlib
import re
import sys

DATA_TYPES = {'1': 'Number', '2': 'Char', '3': 'Date', '5': 'DateTime', '6': 'DateTime'}
UPLOAD_TYPES = {'0': 'Java upload class', '1': 'Table', '2': 'API', '4': 'Download only', '5': 'API'}
ENV_DEFAULTS = {'SYSDATE': 'sysdate', 'OAUSER.ID': 'fnd_global.user_id', 'DATABASE': None}
ENV_TOKENS = {'userid': 'fnd_global.user_id', 'respid': 'fnd_global.resp_id', 'appid': 'fnd_global.resp_appl_id', 'language': "userenv('lang')"}
TOKEN = re.compile(r'"((?:[^"\\]|\\[\s\S])*)"|(\n)|([^\s"=]+)|(=)')
SEED_OWNER = re.compile(r'^(ORACLE|SEED|ANONYMOUS)', re.I)


def unescape(s):
    s = re.sub(r'\\n\\\r?\n', '\n', s)
    s = re.sub(r'\\\r?\n', '', s)
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t'}.get(m.group(1), m.group(1)), s)


def parse(path):
    """FNDLOAD ldt -> tree of {entity, keys, attrs: {name: [values]}, children}"""
    text = pathlib.Path(path).read_text(encoding='utf-8', errors='replace')
    start = re.search(r'^\s*BEGIN ', text, re.M)
    text = text[start.start():] if start else ''
    toks = []
    for m in TOKEN.finditer(text):
        if m.group(1) is not None:
            toks.append(('S', unescape(m.group(1))))
        elif m.group(2):
            toks.append(('NL', None))
        elif m.group(3):
            toks.append(('W', m.group(3)))
        else:
            toks.append(('EQ', None))
    root = {'entity': 'ROOT', 'keys': [], 'attrs': {}, 'children': []}
    stack = [root]
    i, n = 0, len(toks)
    while i < n:
        t, v = toks[i]
        if t == 'W' and v == 'BEGIN' and i + 1 < n:
            ent, i = toks[i + 1][1], i + 2
            keys = []
            while i < n and toks[i][0] == 'S':
                keys.append(toks[i][1])
                i += 1
            node = {'entity': ent, 'keys': keys, 'attrs': {}, 'children': []}
            stack[-1]['children'].append(node)
            stack.append(node)
        elif t == 'W' and v == 'END':
            if len(stack) > 1:
                stack.pop()
            i += 2
        elif t == 'W' and i + 1 < n and toks[i + 1][0] == 'EQ':
            i += 2
            while i < n and toks[i][0] == 'NL':
                i += 1
            vals = []
            while i < n and toks[i][0] == 'S':
                vals.append(toks[i][1])
                i += 1
            stack[-1]['attrs'][v] = vals
        else:
            i += 1
    return root


def walk(node, ent):
    for c in node['children']:
        if c['entity'] == ent:
            yield c
        yield from walk(c, ent)


def a(node, k):
    return ' '.join(x for x in node['attrs'].get(k, []) if x).strip() if node else ''


def ref(node, k):
    """A reference attribute ("APP" "CODE") as its code, '' when empty."""
    vals = [x for x in node['attrs'].get(k, []) if x] if node else []
    return vals[-1] if vals else ''


def translate(text, issues, where):
    """WebADI tokens to Blitz Report binds; anything unknown is reported, never guessed."""
    if not text:
        return text
    t = re.sub(r'\$PROFILES\$\.([A-Za-z0-9_]+)', lambda m: f"fnd_profile.value('{m.group(1).upper()}')", text, flags=re.I)
    t = re.sub(r'\$PARAM\$\.([A-Za-z0-9_:]+)', lambda m: f':$flex$.{m.group(1)}', t, flags=re.I)
    t = re.sub(r'\$(TABLE|INTERFACE)\$\.(?:[A-Za-z0-9_]+\.)?([A-Za-z0-9_]+)', lambda m: f':$column$.{m.group(2).lower()}', t, flags=re.I)

    def env(m):
        rep = ENV_TOKENS.get(m.group(1).lower())
        if not rep:
            issues.append(f'{where}: no equivalent known for `{m.group(0)}`')
        return rep or m.group(0)
    t = re.sub(r'\$ENV\$\.([A-Za-z_]+)', env, t, flags=re.I)
    for left in sorted(set(re.findall(r'(?<!:)\$[A-Za-z_]+\$(?:\.[A-Za-z0-9_.:]+)?', t))):
        issues.append(f'{where}: no equivalent known for `{left}`')
    return t


def split_columns(text):
    """Split a select list on the commas outside brackets and quotes."""
    parts, depth, quote, cur = [], 0, False, ''
    for ch in text:
        if ch == "'":
            quote = not quote
        elif not quote and ch == '(':
            depth += 1
        elif not quote and ch == ')':
            depth -= 1
        if ch == ',' and not quote and depth == 0:
            parts.append(cur.strip())
            cur = ''
        else:
            cur += ch
    return [p for p in parts + [cur.strip()] if p]


def strip_alias(expr):
    m = re.match(r'^(.*[\w)\'"])\s+"?[A-Za-z_][A-Za-z0-9_$#]*"?$', expr, re.S)
    return m.group(1).strip() if m and not re.fullmatch(r'distinct', m.group(1).strip(), re.I) else expr.strip()


def md(s, width=None):
    s = re.sub(r'\s+', ' ', s or '').strip().replace('|', '\\|')
    return s if not width or len(s) <= width else s[:width - 3] + '...'


class Integrator:
    def __init__(self, ldt, prefixes):
        self.ldt = pathlib.Path(ldt)
        self.folder = self.ldt.parent
        self.prefixes = prefixes
        self.issues = []
        self.java = []
        root = parse(ldt)
        self.root = root
        integ = next(walk(root, 'BNE_INTEGRATORS'), None)
        self.node = integ
        self.asn, self.code = (integ['keys'] + ['', ''])[:2] if integ else ('', self.ldt.stem.replace('_integrator', ''))
        self.name = a(integ, 'USER_NAME') or self.code
        self.owner = a(integ, 'OWNER')
        self.attributes = {n['keys'][-1]: n for n in walk(root, 'BNE_ATTRIBUTES') if n['keys']}
        self.lists = {n['keys'][-1]: n for n in walk(root, 'BNE_PARAM_LISTS') if n['keys']}
        self.defns = {n['keys'][-1]: n for n in walk(root, 'BNE_PARAM_DEFNS') if n['keys']}
        self.components = {n['keys'][-1]: n for n in walk(root, 'BNE_COMPONENTS') if n['keys']}
        self.interfaces = list(walk(root, 'BNE_INTERFACES'))
        self.layouts = list(walk(root, 'BNE_LAYOUTS'))
        self.contents = list(walk(root, 'BNE_CONTENTS'))
        self.mappings = list(walk(root, 'BNE_MAPPINGS'))
        self.rules = [a(r, 'SECURITY_VALUE') for r in walk(root, 'BNE_SECURITY_RULES')]
        upload = [i for i in self.interfaces if a(i, 'UPLOAD_TYPE') not in ('4', '')]
        if not self.interfaces and not self.contents:
            self.kind = 'No interface'
        elif upload:
            self.kind = 'Upload'
        elif self.interfaces:
            self.kind = 'Download only'
        else:
            self.kind = 'No interface'

    # parameter lists
    def items(self, code):
        lst = self.lists.get(code)
        if not lst:
            return []
        return sorted((c for c in lst['children'] if c['entity'] == 'BNE_PARAM_LIST_ITEMS'), key=lambda c: int(c['keys'][-1]) if c['keys'] and c['keys'][-1].isdigit() else 0)

    def item_attr(self, item):
        return self.attributes.get(ref(item, 'LIST_ITEM'))

    def item_value(self, item):
        v = a(item, 'STRING_VALUE') or a(item, 'NUMBER_VALUE') or a(item, 'DATE_VALUE')
        if not v:
            d = self.defns.get(ref(item, 'DEFN'))
            v = a(d, 'DEFAULT_STRING') or a(d, 'DEFAULT_STRING_TRANS') or a(d, 'DEFAULT_NUMBER') or a(d, 'DEFAULT_DATE')
        return v

    def list_target(self, code):
        """The procedure or function a parameter list resolves to, from the attribute row its LIST names."""
        att = self.attributes.get(ref(self.lists.get(code), 'LIST'))
        return (a(att, 'ATTRIBUTE1'), a(att, 'ATTRIBUTE2')) if att else ('', '')

    def is_custom(self, name):
        return bool(name) and any(re.match(rf'^{re.escape(p)}', name, re.I) for p in self.prefixes)

    # columns
    def columns(self, intf):
        cols = []
        for c in intf['children']:
            if c['entity'] != 'BNE_INTERFACE_COLS':
                continue
            g = lambda k: a(c, k)
            cols.append({
                'seq': int(c['keys'][-1]) if c['keys'] and c['keys'][-1].isdigit() else 0,
                'name': g('INTERFACE_COL_NAME'), 'alias': g('INTERFACE_COL_TYPE') == '2',
                'prompt': g('PROMPT_LEFT') or g('PROMPT_ABOVE') or g('INTERFACE_COL_NAME'),
                'type': DATA_TYPES.get(g('DATA_TYPE'), g('DATA_TYPE') or '-'), 'size': g('FIELD_SIZE'),
                'enabled': g('ENABLED_FLAG') == 'Y', 'required': g('REQUIRED_FLAG') == 'Y', 'display': g('DISPLAY_FLAG') == 'Y',
                'read_only': g('READ_ONLY_FLAG') == 'Y', 'dtype': g('DEFAULT_TYPE'), 'dvalue': g('DEFAULT_VALUE'),
                'vtype': g('VAL_TYPE'), 'vobj': g('VAL_OBJ_NAME'), 'vid': g('VAL_ID_COL'), 'vmean': g('VAL_MEAN_COL'),
                'vdesc': g('VAL_DESC_COL'), 'vwhere': g('VAL_ADDL_W_C'), 'vcomp': ref(c, 'VAL_COMPONENT'), 'lov': g('LOV_TYPE'),
                'group': g('GROUP_NAME'), 'segment': g('SEGMENT_NUMBER'), 'flex': g('OA_FLEX_CODE'), 'flex_app': g('OA_FLEX_APPLICATION_ID'),
                'flex_num': g('OA_FLEX_NUM'), 'param_item': g('UPLOAD_PARAM_LIST_ITEM_NUM'), 'expanded': g('EXPANDED_SQL_QUERY'), 'hint': g('USER_HINT'),
            })
        return sorted(cols, key=lambda x: x['seq'])

    def layout_rows(self, layout, intf_code):
        """(block name, block element, layout column, interface column seq) in sheet order for one interface."""
        rows = []
        blocks = [b for b in layout['children'] if b['entity'] == 'BNE_LAYOUT_BLOCKS']
        for b in sorted(blocks, key=lambda b: int(a(b, 'SEQUENCE_NUM') or 0)):
            lcols = [c for c in b['children'] if c['entity'] == 'BNE_LAYOUT_COLS' and a(c, 'INTERFACE_CODE') == intf_code]
            for lc in sorted(lcols, key=lambda c: int(c['keys'][-1]) if c['keys'][-1].isdigit() else 0):
                rows.append((a(b, 'USER_NAME') or a(b, 'LAYOUT_ELEMENT'), a(b, 'LAYOUT_ELEMENT'), lc, int(a(lc, 'INTERFACE_SEQ_NUM') or 0)))
        return rows

    def default_text(self, dtype, dvalue, where):
        if not dtype:
            return ''
        t = dtype.upper()
        if t == 'CONSTANT':
            return f"'{dvalue}'"
        if t == 'SQL':
            return translate(dvalue, self.issues, where)
        if t == 'ENVIRONMENT':
            if dvalue.upper() in ENV_DEFAULTS:
                return ENV_DEFAULTS[dvalue.upper()] or '(document context only, no column)'
            self.issues.append(f'{where}: environment default `{dvalue}` has no known equivalent')
            return f'ENVIRONMENT {dvalue}'
        if t == 'PARAMETER':
            return f':$flex$.{dvalue}'
        if t == 'PROFILE':
            return f"fnd_profile.value('{dvalue.upper()}')"
        if t == 'TABLELOOKUP':
            return translate(dvalue, self.issues, where)
        if t == 'SEQUENCE_EACH_ROW':
            return f'{dvalue.lower()}.nextval in the procedure, per row'
        if t.startswith('JAVA'):
            self.java.append((where.split('`')[1] if '`' in where else where, dvalue, f'default ({dtype})'))
            return f'{dtype} {dvalue}'
        if t == 'NULL':
            return 'null'
        self.issues.append(f'{where}: default type {dtype} `{dvalue}` not mapped')
        return f'{dtype} {dvalue}'

    def validation(self, c, where):
        vt = c['vtype'].upper()
        if vt == 'TABLE':
            distinct = any(re.match(r'\s*distinct\s', x, re.I) for x in (c['vid'], c['vmean']))
            col = lambda x: re.sub(r'^\s*distinct\s+', '', x, flags=re.I).strip()
            vid, vmean = col(c['vid']), col(c['vmean']) or col(c['vid'])
            sel = [f'{vid} id'] if vid and vid != vmean else []
            sel.append(f'{vmean} value')
            descs = [strip_alias(x) for x in split_columns(c['vdesc'])]
            sel.append(("||', '||".join(descs) if descs else 'null') + ' description')
            sql = f"select {'distinct ' if distinct else ''}{', '.join(sel)} from {c['vobj']}"
            if c['vwhere']:
                where_clause = translate(c['vwhere'], self.issues, where).strip()
                sql += ' ' + (where_clause if re.match(r'(where|order\s+by)\b', where_clause, re.I) else 'where ' + where_clause)
            return 'Table', sql
        if vt in ('KEYFLEX', 'KEYFLEXID', 'ACCTFLEX'):
            return 'Key flexfield', f"{c['flex']} (application {c['flex_app']}, structure {translate(c['flex_num'], self.issues, where) or '-'})" + (' returns the combination id' if vt == 'KEYFLEXID' else '')
        if vt in ('KEYFLEXSEG', 'KEYFLEXIDSEG'):
            return 'Key flexfield segment', f"segment {c['segment']} of group {c['group']}"
        if vt in ('DESCFLEX', 'DESCFLEXCONTEXT'):
            return 'Descriptive flexfield' + (' context' if vt.endswith('CONTEXT') else ''), f"{c['flex']} (application {c['flex_app']})"
        if vt == 'DESCFLEXSEG':
            return 'Descriptive flexfield segment', f"segment {c['segment']} of group {c['group']}"
        if vt == 'EXPANDEDSQLSEG':
            return 'Expanded SQL segment', f"segment {c['segment']} of group {c['group']}"
        if vt == 'EXPANDEDSQL':
            self.issues.append(f"{where}: expanded SQL column set of group `{c['group']}` (a variable number of columns built when the document is created); decide the Blitz row design, usually one row per expanded value")
            return 'Expanded SQL', md(translate(c['expanded'], self.issues, where), 300)
        if vt in ('JAVA', 'GROUP'):
            self.java.append((c['name'], c['vobj'], 'validator' if vt == 'JAVA' else 'cross-column validator'))
            return 'Java' if vt == 'JAVA' else 'Group', c['vobj']
        if vt in ('', 'CALENDAR'):
            return '', ''
        self.issues.append(f'{where}: validation type {vt} not mapped')
        return vt, c['vobj']

    def api(self, intf):
        """(kind, target, [(item no, parameter, type, direction, literal)]) of an interface."""
        ut = a(intf, 'UPLOAD_TYPE')
        if ut == '1':
            return 'Table', a(intf, 'INTERFACE_NAME'), []
        if ut == '0':
            return 'Java upload class', a(intf, 'UPLOAD_OBJ_NAME'), []
        code = ref(intf, 'UPLOAD_PARAMS')
        kind, target = self.list_target(code)
        args = []
        for it in self.items(code):
            att = self.item_attr(it)
            args.append((it['keys'][-1], a(att, 'ATTRIBUTE1') or a(it, 'PARAM_NAME'), a(att, 'ATTRIBUTE2'), a(att, 'ATTRIBUTE3'), a(att, 'ATTRIBUTE5')))
        return (kind.title() if kind else 'API'), target or a(intf, 'INTERFACE_NAME'), args

    def importer(self):
        """Importer steps: [(step, list code, description, [(name, value, attribute summary)])]"""
        steps = []
        for it in self.items(ref(self.node, 'IMPORT')):
            sub = a(it, 'STRING_VALUE').split(':')[-1]
            rows = []
            for s in self.items(sub):
                att = self.item_attr(s)
                attrs = ' '.join(f'{k[9:]}={a(att, k)}' for k in sorted(att['attrs'], key=lambda k: int(k[9:]) if k[9:].isdigit() else 99) if k.startswith('ATTRIBUTE') and a(att, k)) if att else ''
                rows.append((a(s, 'PARAM_NAME'), self.item_value(s), attrs))
            desc = a(it, 'DESC_VALUE') or a(self.lists.get(sub), 'USER_NAME') if sub in self.lists else self.item_value(it)
            steps.append((a(it, 'PARAM_NAME'), sub if sub in self.lists else '', desc, rows))
        return steps

    def programs(self):
        """Concurrent programs the importer submits: [(application, program)]"""
        out = []
        for step, _, _, rows in self.importer():
            if step.upper() != 'CONCURRENT_REQUEST':
                continue
            vals = {}
            for name, value, attrs in rows:
                m = re.search(r'(?:^| )1=(APPLICATION|PROGRAM)\b.*?(?:^| )5=(\S+)', attrs)
                if m:
                    vals[m.group(1)] = m.group(2).strip("'")
            if vals.get('PROGRAM'):
                out.append((vals.get('APPLICATION', ''), vals['PROGRAM']))
        return out

    def uploader(self):
        """Upload page parameters: [(name, value, visible, user can change)]"""
        out = []
        for it in self.items(ref(self.node, 'UPL')):
            d = self.defns.get(ref(it, 'DEFN'))
            out.append((a(it, 'PARAM_NAME') or a(d, 'PARAM_NAME'), self.item_value(it), a(d, 'DEFAULT_VISIBLE_FLAG'), a(d, 'DEFAULT_USER_MODIFYABLE_FLAG')))
        return out

    def commit_rows(self):
        for name, value, visible, modifiable in self.uploader():
            if name.lower() == 'bne:commitrows':
                v = (value or '').upper().replace(' ', '_')
                eff = 'Each Row' if v == 'EACH_ROW' else 'All Rows'
                return eff, f"bne:commitrows={value or '(not set)'}, shown {visible or '-'}, user can change {modifiable or '-'}"
        return 'All Rows', 'bne:commitrows not in the upload parameter list (default)'

    def responsibilities(self):
        f = self.folder / f'{self.code}_responsibilities.txt'
        if not f.exists():
            return None
        rows = [l.rstrip('\r\n').split('|') for l in f.read_text(encoding='utf-8', errors='replace').splitlines()[1:] if l.strip()]
        funcs = {}
        for r in rows:
            if len(r) >= 6:
                funcs.setdefault((r[0], r[1], r[2]), set()).add(r[5])
        return funcs

    def document_parameters(self):
        """Parameters the user enters when creating the WebADI document; they become upload parameters."""
        cols = [c for i in self.interfaces for c in self.columns(i) if c['enabled']]
        text = ' '.join(c[k] for c in cols for k in ('dvalue', 'vwhere', 'flex_num', 'expanded'))
        text += ' '.join(a(s, 'QUERY') for ct in self.contents for s in walk(ct, 'BNE_STORED_SQL'))
        names = {m.group(1) for m in re.finditer(r'\$PARAM\$\.([A-Za-z0-9_:]+)', text, re.I)}
        names |= {c['dvalue'] for c in cols if c['dtype'].upper() == 'PARAMETER' and c['dvalue']}
        return sorted(names, key=str.lower)

    def gathered_objects(self):
        return sorted(p.name for p in self.folder.glob('*.sql'))

    def referenced_custom(self):
        text = self.ldt.read_text(encoding='utf-8', errors='replace')
        names = set()
        for p in self.prefixes:
            for m in re.finditer(rf'(?<![A-Za-z0-9_$#]){re.escape(p)}[A-Za-z0-9_$#]*(?:\.[A-Za-z0-9_$#]+)?', text, re.I):
                names.add(m.group(0).upper())
        return sorted(names)


def shipped_candidates(integ, content_dir):
    if not content_dir or not content_dir.is_dir():
        return []
    needles = set()
    for intf in integ.interfaces:
        kind, target, _ = integ.api(intf)
        if target:
            needles.add(target.split('.')[0].lower())
    needles |= {p.lower() for _, p in integ.programs()}
    prefixes = {t.split('_')[0].upper() for t in needles if '_' in t} | {integ.asn.upper()}
    strong, weak = [], []
    for f in sorted(content_dir.glob('*.xml')):
        text = f.read_text(encoding='utf-8', errors='replace')
        m = re.search(r'<REPORT_NAME>([^<]+)</REPORT_NAME>', text)
        if not m:
            continue
        name = m.group(1)
        low = text.lower()
        if any(re.search(rf'\b{re.escape(n)}\b', low) for n in needles):
            strong.append(name)
        elif name.split(' ')[0].upper() in prefixes:
            weak.append(name)
    return [f'{n} (names the same interface, package or program)' for n in strong] + weak[:8]


def module_package(integ, extensions_dir):
    """The XXEN_<MODULE>_UPLOAD package the upload procedure goes into: the product code of the API or table written."""
    for intf in integ.interfaces:
        if a(intf, 'UPLOAD_TYPE') in ('1', '2', '5'):
            obj = integ.api(intf)[1].split('.')[0].upper()
            if obj and '_' in obj and not integ.is_custom(obj):
                package = f"XXEN_{obj.split('_')[0]}_UPLOAD"
                if not extensions_dir:
                    return f'`{package}` (check whether `sql/extensions` has it)'
                return f"`{package}` ({'exists: add the procedure' if (extensions_dir / f'{package}.pks').exists() else 'new: create it'})"
    integ.issues.append('the integrator writes through customer objects only: take the package module from the product code of the tables they write')
    return 'the module of the tables the customer objects write (section 12)'


def write_fad(integ, content_dir, abbrev, extensions_dir=None):
    L = []
    w = L.append
    custom = not SEED_OWNER.match(integ.owner or 'ORACLE')
    w(f'# Form Analysis Document: {integ.name}\n')
    w(f'Source: WebADI integrator `{integ.asn}:{integ.code}`, definition `{integ.ldt.name}`. Generated by `webadi_fad.py`; review every section before building.\n')
    w('## 1. Summary\n')
    w('| Item | Value |\n|---|---|')
    w(f'| Integrator | {md(integ.name)} (`{integ.code}`, application `{integ.asn}`) |')
    w(f"| Built by | {'the customer (row owner ' + integ.owner + ')' if custom else 'Oracle (row owner ' + (integ.owner or '-') + ')'} |")
    for intf in integ.interfaces:
        kind, target, args = integ.api(intf)
        w(f"| Interface `{intf['keys'][-1]}` | {UPLOAD_TYPES.get(a(intf, 'UPLOAD_TYPE'), a(intf, 'UPLOAD_TYPE'))}: `{target}`{' (customer object)' if integ.is_custom(target) else ''} |")
    eff, detail = integ.commit_rows()
    w(f'| Commit | {eff}: {md(detail)} |')
    progs = integ.programs()
    steps = integ.importer()
    w(f"| Importer | {', '.join(s[0] for s in steps) or 'none'}{'; submits ' + ', '.join(f'`{p}` ({ap})' for ap, p in progs) if progs else ''} |")
    params = integ.document_parameters()
    w(f"| Document parameters | {', '.join(f'`{p}`' for p in params) + ' (each becomes an upload parameter: rename `:$flex$.<name>` in the drafts below to its Blitz parameter name)' if params else 'none'} |")
    cands = shipped_candidates(integ, content_dir)
    w(f"| Shipped upload candidates | {'; '.join(cands) if cands else 'none found' if content_dir else 'not checked (no content folder)'} |")
    w(f"| Category if built new | `Custom Uploads {abbrev or '<ABBR>'}` |")
    package = module_package(integ, extensions_dir)
    w(f'| Upload package | {package} |\n')

    for intf in integ.interfaces:
        if a(intf, 'UPLOAD_TYPE') == '4':
            continue
        icode = intf['keys'][-1]
        cols = integ.columns(intf)
        byseq = {c['seq']: c for c in cols}
        kind, target, args = integ.api(intf)
        w(f'## 2. Visual field order: interface `{icode}`\n')
        if not integ.layouts:
            w('No layout in the definition: the column order below is the interface display order.\n')
        for lay in integ.layouts:
            rows = integ.layout_rows(lay, icode)
            if not rows:
                continue
            w(f"Layout `{lay['keys'][-1]}` {md(a(lay, 'USER_NAME'))}. Context and header block values apply to the whole sheet in WebADI: each becomes an upload parameter or a column repeated on every row; the Database context value has no equivalent.\n")
            w('| # | Block | Prompt | Interface column | Type | Req | Read only | List | Default |\n|---|---|---|---|---|---|---|---|---|')
            for i, (bname, elem, lc, seq) in enumerate(rows, 1):
                c = byseq.get(seq)
                if not c:
                    integ.issues.append(f'layout `{lay["keys"][-1]}` names interface column {seq}, which the interface does not have')
                    continue
                where = f"column `{c['name']}`"
                ro = a(lc, 'READ_ONLY_FLAG') == 'Y' or c['read_only']
                dflt = integ.default_text(a(lc, 'DEFAULT_TYPE') or c['dtype'], a(lc, 'DEFAULT_VALUE') or c['dvalue'], where)
                vkind, _ = integ.validation(c, where)
                w(f"| {i} | {md(bname)} | {md(c['prompt'])} | {c['name']} | {c['type']} | {'Y' if c['required'] else ''} | {'Y' if ro else ''} | {vkind} | {md(dflt, 120)} |")
            w('')
        w(f'## 3. Field inventory: interface `{icode}`\n')
        w('Enabled columns only. `Alias` columns are not passed to the API or table; they feed lists, flexfields and other columns.\n')
        w('| Seq | Column | Prompt | Type | Size | Req | Shown | Alias | API parameter |\n|---|---|---|---|---|---|---|---|---|')
        argmap = {n: (p, t, d) for n, p, t, d, _ in args}
        for c in cols:
            if not c['enabled']:
                continue
            p = argmap.get(c['param_item'])
            w(f"| {c['seq']} | {c['name']} | {md(c['prompt'])} | {c['type']} | {c['size']} | {'Y' if c['required'] else ''} | {'Y' if c['display'] else ''} | {'Y' if c['alias'] else ''} | {f'{p[0]} {p[1]} {p[2]}' if p else ''} |")
        w('')
        w('## 4. Defaulting map\n')
        w('| Column | WebADI default | Blitz equivalent |\n|---|---|---|')
        for c in cols:
            if c['enabled'] and c['dtype']:
                w(f"| {c['name']} | {c['dtype']}: {md(c['dvalue'], 120)} | {md(integ.default_text(c['dtype'], c['dvalue'], 'column `' + c['name'] + '`'), 160)} |")
        w('')
        w('## 5. Validation and list of values map\n')
        w('| Column | Validation | List SQL or object | List type |\n|---|---|---|---|')
        for c in cols:
            if not c['enabled'] or not c['vtype']:
                continue
            vkind, detail = integ.validation(c, f"column `{c['name']}`")
            comp = integ.components.get(c['vcomp'])
            comp_txt = f" component {a(comp, 'COMPONENT_JAVA_CLASS')}" if comp else ''
            w(f"| {c['name']} | {vkind} | `{md(detail)}` | {c['lov'] or '-'}{comp_txt} |")
        flexes = sorted({(c['vtype'], c['flex'], c['flex_app'], c['group']) for c in cols if c['enabled'] and c['flex']})
        if flexes:
            w('\nFlexfields: ' + '; '.join(f'{f} ({vt}, application {ap}, group {g})' for vt, f, ap, g in flexes) + '. Build key flexfield columns per the KFF rules of upload-development and descriptive flexfields with the add-dff-to-upload skill.')
        w('')
        w('## 6. API / interface details\n')
        if kind == 'Table':
            w(f'Rows are inserted into `{target}`; the importer below processes them. Interface columns of type Alias are not table columns.\n')
        else:
            w(f'`{target}` is called once per row ({kind.lower()}). Parameters in call order:\n')
            w('| # | Parameter | Type | Direction | Fixed value | Interface column |\n|---|---|---|---|---|---|')
            colmap = {c['param_item']: c['name'] for c in cols if c['param_item']}
            for n, p, t, d, lit in args:
                w(f'| {n} | {p} | {t} | {d} | {md(lit)} | {colmap.get(n, "")} |')
            w('')
            if integ.is_custom(target.split('.')[0]):
                obj = target.split('.')[0].upper()
                if not any(obj in f.upper() for f in integ.gathered_objects()):
                    integ.issues.append(f'customer package `{obj}` is not among the gathered .sql files')
    w('## 7. Importer\n')
    if not steps:
        w('None: the upload calls end the processing.\n')
    for step, code, desc, rows in steps:
        w(f"**{step}**{' (`' + code + '`)' if code else ''} {md(desc)}\n")
        if rows:
            w('| Name | Value | Attributes |\n|---|---|---|')
            for name, value, attrs in rows:
                v = md(translate(value, integ.issues, 'importer ' + step), 200)
                w(f"| {md(name)} | {'`' + v + '`' if v else ''} | {md(attrs, 160)} |")
            w('')
    for ap, p in progs:
        if integ.is_custom(p):
            integ.issues.append(f'importer program `{p}` ({ap}) is customer-built: gather it as a concurrent program in a converter run')
    w('## 8. Download content\n')
    if not integ.contents:
        w('None: the integrator creates new rows only.\n')
    for ct in integ.contents:
        cls = a(ct, 'CONTENT_CLASS')
        sqls = [a(s, 'QUERY') for s in walk(ct, 'BNE_STORED_SQL')]
        w(f"**{md(a(ct, 'USER_NAME'))}** (`{ct['keys'][-1]}`){' class ' + cls if cls else ''}\n")
        for q in sqls:
            w('```sql\n' + translate(q, integ.issues, f"content `{ct['keys'][-1]}`").strip() + '\n```\n')
        if cls and not sqls and not cls.startswith('oracle.apps.bne'):
            integ.issues.append(f'download content `{ct["keys"][-1]}` is produced by Java class `{cls}`')
    w('## 9. Access\n')
    w(f"Security rule functions: {', '.join(f'`{r}`' for r in integ.rules) or 'none'}.\n")
    funcs = integ.responsibilities()
    if funcs is None:
        w('No responsibilities file.\n')
    else:
        w('| Function | Type | Name | Responsibilities |\n|---|---|---|---|')
        for (fn, ft, un), resps in sorted(funcs.items(), key=lambda x: -len(x[1])):
            w(f'| {fn} | {ft} | {md(un)} | {len(resps)} |')
        forms = [fn for (fn, ft, _) in funcs if ft == 'FORM']
        w('\n' + (f"Function assignment candidates (FORM): {', '.join(forms)}." if forms else 'No FORM function: assign the upload to the update function of the form that maintains the entity, or leave it without assignment.') + '\n')
    w('## 10. Customer objects\n')
    objs = integ.gathered_objects()
    refs = integ.referenced_custom()
    w(f"Gathered: {', '.join(objs) or 'none'}.\n")
    w(f"Customer-prefixed names in the definition: {', '.join(refs) or 'none'}.\n")
    w('## 11. Upload design recommendations\n')
    w(f"- Outcome: {'template of ' + cands[0].split(' (')[0] + ' if it covers the columns of section 2, otherwise ' if cands else ''}a new upload in `Custom Uploads {abbrev or '<ABBR>'}`.")
    w(f'- Package: {package}. Call customer objects, and APIs that not every release of the package has, through `execute immediate` only.')
    w(f"- Commit: {eff}." + (' Single-call mode with one savepoint for the whole file: any rejected row errors every row.' if eff == 'All Rows' else ' Row by row.'))
    if any(s[0].upper() == 'GROUP' for s in steps):
        grp = next(s for s in steps if s[0].upper() == 'GROUP')
        w(f"- The importer runs once per distinct {', '.join(r[0] for r in grp[3])}: a post procedure with those columns as its IN parameters.")
    w('- Columns: the layout order of section 2; context and header values become upload parameters or columns repeated on every row; required interface columns outside the layout come from their defaults or the procedure.')
    sql_download = any(next(walk(ct, 'BNE_STORED_SQL'), None) for ct in integ.contents)
    java_download = any(a(ct, 'CONTENT_CLASS') and not a(ct, 'CONTENT_CLASS').startswith('oracle.apps.bne.') and not next(walk(ct, 'BNE_STORED_SQL'), None) for ct in integ.contents)
    w('- Upload mode: ' + ('Create and Update, the main SQL from the download content of section 8.' if sql_download else 'Create and Update, the main SQL written from what the Java download class of section 8 returns.' if java_download else 'Create only: the integrator downloads nothing.'))
    w('')
    w('## 12. Open questions\n')
    seen = list(dict.fromkeys(integ.issues))
    java = list(dict.fromkeys(integ.java))
    w('\n'.join(f'- {i}' for i in seen) if seen or java else '- none found by the extraction')
    if java:
        w('- Java logic runs in the WebADI middle tier and the upload must reproduce it in PL/SQL; read what each class checks or derives from the API source, an Oracle class from the instance, a customer class from the source the customer supplies:')
        w('\n'.join(f"  - `{col}` {kind} " + (f"`{cls}`" + ('' if cls.startswith('oracle.apps.') else ' (customer class)') if cls else '(no class named)') for col, cls, kind in java))
    out = integ.folder / f'FAD_{integ.code}.md'
    out.write_text('\n'.join(L) + '\n', encoding='utf-8')
    return out, len(seen) + len(java)


def write_download(integ):
    """A download-only integrator is a report: its download SQL, one block per layout's content."""
    L = [f'# Download SQL: {integ.name}\n', f'WebADI integrator `{integ.asn}:{integ.code}` uploads nothing; convert it as a report. `:$flex$.<name>` marks a document parameter, which becomes a report parameter.\n']
    for ct in integ.contents:
        sqls = [a(s, 'QUERY') for s in walk(ct, 'BNE_STORED_SQL')]
        if sqls:
            L.append(f"## {md(a(ct, 'USER_NAME'))} (`{ct['keys'][-1]}`)\n")
            L += ['```sql\n' + translate(q, integ.issues, ct['keys'][-1]).strip() + '\n```\n' for q in sqls]
    if integ.issues:
        L.append('## Open questions\n')
        L += [f'- {i}' for i in dict.fromkeys(integ.issues)]
    out = integ.folder / f'{integ.code}_download_sql.md'
    out.write_text('\n'.join(L) + '\n', encoding='utf-8')
    return out


def manifest(folder):
    f = folder / 'manifest.txt'
    vals = {}
    if f.exists():
        for line in f.read_text(encoding='utf-8', errors='replace').splitlines():
            if ':' in line and not line.startswith(' '):
                k, v = line.split(':', 1)
                vals[k.strip()] = v.strip()
    return vals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path')
    ap.add_argument('--content', help='folder of shipped upload XMLs (default: BLITZ_CONTENT_DIR, else content/r12/uploads of the repository)')
    ap.add_argument('--extensions', help='folder of the upload packages (default: sql/extensions of the repository)')
    args = ap.parse_args()
    path = pathlib.Path(args.path)
    if path.is_file():
        ldts, root = [path], path.parent
    else:
        ldts, root = sorted(path.glob('*_integrator.ldt')) or sorted(path.glob('*/*_integrator.ldt')), path
    if not ldts:
        sys.exit(f'no *_integrator.ldt under {path}')
    meta = manifest(root if (root / 'manifest.txt').exists() else root.parent)
    prefixes = [p.strip() for p in re.split(r'[,;\s]+', meta.get('custom_object_prefix', '')) if p.strip()]
    abbrev = meta.get('customer_abbreviation', '')
    repo = pathlib.Path(__file__).resolve().parents[3]
    content = pathlib.Path(args.content or os.environ.get('BLITZ_CONTENT_DIR') or repo / 'content' / 'r12' / 'uploads')
    extensions = pathlib.Path(args.extensions) if args.extensions else repo / 'sql' / 'extensions'
    inv = ['# WebADI integrator inventory\n', '| Integrator | Name | Kind | Interfaces | Importer | Commit | Layout columns | Open questions | Next step |', '|---|---|---|---|---|---|---|---|---|']
    for ldt in ldts:
        integ = Integrator(ldt, prefixes)
        targets = '; '.join(f"{UPLOAD_TYPES.get(a(i, 'UPLOAD_TYPE'), a(i, 'UPLOAD_TYPE'))} `{integ.api(i)[1]}`" for i in integ.interfaces) or '-'
        nlay = sum(len(integ.layout_rows(l, i['keys'][-1])) for l in integ.layouts for i in integ.interfaces if a(i, 'UPLOAD_TYPE') != '4')
        if integ.kind == 'Upload':
            fad, nq = write_fad(integ, content if content.is_dir() else None, abbrev, extensions if extensions.is_dir() else None)
            nxt = f'build from `{fad.name}`'
        elif integ.kind == 'Download only':
            nq, nxt = 0, f'a report: convert `{write_download(integ).name}` with the custom reports path'
        else:
            nq, nxt = 0, 'nothing to convert: ask what the customer uploads with it'
        prog = ', '.join(p for _, p in integ.programs()) or ', '.join(s[0] for s in integ.importer()) or '-'
        inv.append(f"| `{integ.code}` | {md(integ.name)} | {integ.kind} | {md(targets, 140)} | {md(prog, 60)} | {integ.commit_rows()[0] if integ.kind == 'Upload' else '-'} | {nlay or '-'} | {nq or '-'} | {nxt} |")
        print(f'{integ.code}: {integ.kind}' + (f', {nq} open question(s)' if integ.kind == 'Upload' else ''))
    (root / 'webadi_inventory.md').write_text('\n'.join(inv) + '\n', encoding='utf-8')
    print(f"wrote {root / 'webadi_inventory.md'}")


if __name__ == '__main__':
    main()
