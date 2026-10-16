#!/usr/bin/env python
"""Lint a Blitz Upload XML file against the Upload Completeness Checklist
in `.claude/rules/public/upload-development.md`. Exit code 0 = clean, non-zero = violations.

Usage:
  python tools/lint_upload_xml.py <upload.xml> [<upload.xml>...]
  python tools/lint_upload_xml.py --all          (every r12 upload, all rules)
  python tools/lint_upload_xml.py --all-content  (every content XML, always-on rules only)

Rules checked (IDs match the Upload Completeness Checklist):
  A1     Mandatory framework columns: action_, status_, message_, modified_columns_, upload_row
  A3     UPLOAD_COLUMNS_ROW column numbers sequential 1..N
  A3T    Visible TEMPLATE_COLUMNS_ROW display sequences sequential 1..N (no midpoint decimals)
  B7     UPLOAD_PARAMETERS_ROW with COLUMN_NAME must reference an existing UPLOAD_COLUMNS_ROW (or framework internal)
  D2/D3  Yes-LOV pattern: column whose LOV_QUERY matches the canonical Yes-only pattern
         must use COLUMN_TYPE=LOV with LOV_NAME=Yes + LOV_GUID=8E2FF36EDEA679D2E0530100007F1FF2
  G1     Upload Mode parameter must use shared LOV (LOV_NAME=Blitz Upload Mode + GUID)
  G2     Upload Mode must bind `:p_upload_mode`, in SQL_TEXT or as the ANCHOR
  G4     Upload Mode parameter REQUIRED=Y
  H1     Error SQL row exists with NO SQL_TEXT (auto-generated)
  H2     Order By row exists
  H3     Success SQL row exists
  H3b    Success SQL must be Oracle-sourced (nvl(oracle, xu)), not a bare `xu` echo
         (flagged when the FROM references only the upload view)
  I+5    Read-only descriptor column (name contains DESCRIPTION) must have a DEFAULT_VALUE
         deriving it from its parent key via :$column$.<parent>
  I1     GUID present in REPORTS_ROW
  I2     REPORT_TRANSLATIONS with LANGUAGE=US present
  I7     Upload ASSIGNMENTS must be Function level only
  L1     LOV reuse heuristic: if LOV_QUERY fingerprint matches a known shared LOV
         entity (mtl_system_items_b_kfv with eam_item_type → EAM Asset Group, etc.),
         column should reference that shared LOV via LOV_NAME + LOV_GUID, not be `LOV custom`.
  P1     PARAMETERS_ROW with a DISPLAY_SEQUENCE must carry a PARAMETER_TYPE_DSP
         (checked for reports too, not just uploads)

A file may suppress a specific rule with a documented XML comment, for the rare legitimate case
(e.g. a purge/converter/tool upload that persists nothing to re-query, so an echo Success SQL is correct):
  <!-- lint-ignore: H3b purge upload — nothing persisted to re-query, echo is correct -->
"""
import os, re, sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Shared LOV catalog — fingerprints for the most common reuse opportunities.
# (column_name_pattern, query_fingerprint_regex, expected_lov_name, expected_lov_guid)
# query_fingerprint must match against the LOV_QUERY (entity-decoded) using DOTALL+IGNORECASE.
SHARED_LOV_FINGERPRINTS = [
    # Match only the shared LOV's signature shape (joins to fnd_territories_vl ftv for the
    # rich description and references the operating_unit / ledger param dependencies).
    # Intentionally narrow so customizations that drop those features (e.g. add
    # stock_locator_control_code filter for a locator-only upload) do NOT match.
    (r'.*ORG.*|.*ORGANIZATION.*',
     r'mtl_parameters\b.*organization_code.*fnd_territories_vl\s+ftv',
     'INV Organization Code', '8E2FF36EDEB279D2E0530100007F1FF2'),
    (r'ASSET_GROUP', r'mtl_system_items.*\beam_item_type\b',
     'EAM Asset Group', '8E2FF36EDEEC79D2E0530100007F1FF2'),
    (r'ASSET_NUMBER', r'mtl_eam_asset_numbers_all_v|csi_item_instances.*eam_item_type',
     'EAM Asset Number', '8E2FF36EDEEB79D2E0530100007F1FF2'),
    (r'.*DEPARTMENT', r'\bbom_departments\b',
     'BOM Department (org code dependent)', 'E7CCB27F39531272E0530100007F62B4'),
    (r'.*CATEGORY|.*ITEM_CATEGORY', r'mtl_categories|mtl_item_categories',
     'INV Category (org id dependent)', '8E2FF36EDEFF79D2E0530100007F1FF2'),
    (r'.*WIP.*ACCOUNTING.*|.*ACCOUNTING.*CLASS.*', r'wip_accounting_classes',
     'WIP Class Code (org dependent)', 'E7CCB27F39561272E0530100007F62B4'),
    (r'.*OPERATING_UNIT.*', r'hr_all_organization_units|hr_operating_units',
     'HR Operating Unit', '8E2FF36EDEB979D2E0530100007F1FF2'),
    (r'.*LEDGER.*', r'\bgl_ledgers\b',
     'GL Ledger', '8E2FF36EDEB879D2E0530100007F1FF2'),
]

YES_LOV_PATTERN = re.compile(
    r"select\s+'Y'\s+id\s*,\s*xxen_util\.meaning\(\s*'Y'\s*,\s*'YES_NO'",
    re.IGNORECASE | re.DOTALL
)
YES_LOV_NAME = 'Yes'
YES_LOV_GUID = '8E2FF36EDEA679D2E0530100007F1FF2'

UPLOAD_MODE_LOV_GUID = 'E811F942597A2075E0530100007FF4F2'

# Framework internal column names allowed without a matching UPLOAD_COLUMNS_ROW
FRAMEWORK_INTERNAL_COLS = {'ACTION_CODE_', 'STATUS_CODE_', 'MESSAGE_'}


def decode_xml_entities(s: str) -> str:
    return (s.replace('&apos;', "'")
              .replace('&amp;', '&')
              .replace('&lt;', '<')
              .replace('&gt;', '>')
              .replace('&quot;', '"'))


class UploadLint:
    def __init__(self, path: Path):
        self.path = path
        self.text = path.read_text(encoding='utf-8', errors='replace')
        self.violations = []         # (line_no_1based, rule_id, message)

    def add(self, rule_id, message, search_text=None):
        # documented escape hatch: a file may suppress a specific rule with an XML comment
        # e.g. <!-- lint-ignore: H3b purge upload — nothing persisted to re-query, echo is correct -->
        if f'lint-ignore: {rule_id}' in self.text:
            return
        line_no = 1
        if search_text:
            idx = self.text.find(search_text)
            if idx >= 0:
                line_no = self.text.count('\n', 0, idx) + 1
        self.violations.append((line_no, rule_id, message))

    # ---- Helpers ----

    def _find_blocks(self, tag):
        return re.findall(rf'<{tag}>(.*?)</{tag}>', self.text, flags=re.S)

    def _row_blocks(self, row_tag):
        return re.findall(rf'<{row_tag}>(.*?)</{row_tag}>', self.text, flags=re.S)

    def _get_inner(self, block, tag):
        m = re.search(rf'<{tag}>(.*?)</{tag}>', block, flags=re.S)
        return m.group(1) if m else None

    # ---- Rule implementations ----

    def check_a1_framework_columns(self):
        col_names = set()
        col_blocks = self._row_blocks('UPLOAD_COLUMNS_ROW')
        for b in col_blocks:
            n = self._get_inner(b, 'COLUMN_NAME')
            if n: col_names.add(n.strip().upper())
        # Must have these
        for required in ['ACTION_', 'STATUS_', 'MESSAGE_', 'MODIFIED_COLUMNS_', 'UPLOAD_ROW']:
            if required not in col_names:
                self.add('A1', f'mandatory framework column {required} not found in UPLOAD_COLUMNS')

    def check_a3_sequential_column_numbers(self):
        nums = []
        for b in self._row_blocks('UPLOAD_COLUMNS_ROW'):
            n = self._get_inner(b, 'COLUMN_NUMBER')
            if n and n.strip().isdigit():
                nums.append(int(n.strip()))
        if not nums: return
        for expected, actual in enumerate(nums, start=1):
            if expected != actual:
                self.add('A3', f'UPLOAD_COLUMNS_ROW column_number {actual} not sequential (expected {expected})',
                         search_text=f'<COLUMN_NUMBER>{actual}</COLUMN_NUMBER>')
                break

    def check_a3t_sequential_template_columns(self):
        """Positive display sequences are visible columns and must be 1..N.
        Negative sequences represent hidden columns and retain their own ordering."""
        for template in self._row_blocks('TEMPLATES_ROW'):
            template_name = (self._get_inner(template, 'TEMPLATE_NAME') or '?').strip()
            visible = []
            for row in re.findall(r'<TEMPLATE_COLUMNS_ROW>(.*?)</TEMPLATE_COLUMNS_ROW>',
                                  template, flags=re.S):
                seq_text = (self._get_inner(row, 'DISPLAY_SEQUENCE') or '').strip()
                if not seq_text:
                    continue
                try:
                    sequence = Decimal(seq_text)
                except InvalidOperation:
                    self.add('A3T',
                             f'template {template_name}: non-numeric display_sequence {seq_text!r}',
                             search_text=f'<DISPLAY_SEQUENCE>{seq_text}</DISPLAY_SEQUENCE>')
                    continue
                if sequence > 0:
                    visible.append((sequence, seq_text))
            for expected, (actual, actual_text) in enumerate(sorted(visible), start=1):
                if actual != expected:
                    self.add('A3T',
                             f'template {template_name}: visible display_sequence {actual_text} '
                             f'is not sequential (expected {expected}); renumber all visible columns 1..N',
                             search_text=f'<DISPLAY_SEQUENCE>{actual_text}</DISPLAY_SEQUENCE>')
                    break

    def check_b7_no_orphan_parameters(self):
        col_names = set()
        for b in self._row_blocks('UPLOAD_COLUMNS_ROW'):
            n = self._get_inner(b, 'COLUMN_NAME')
            if n: col_names.add(n.strip().upper())
        for b in self._row_blocks('UPLOAD_PARAMETERS_ROW'):
            cn = self._get_inner(b, 'COLUMN_NAME')
            if cn:
                cn_u = cn.strip().upper()
                if cn_u not in col_names and cn_u not in FRAMEWORK_INTERNAL_COLS:
                    pn = self._get_inner(b, 'PARAMETER_NAME') or '?'
                    self.add('B7', f'UPLOAD_PARAMETERS_ROW PARAMETER_NAME={pn} references COLUMN_NAME={cn_u} which has no matching UPLOAD_COLUMNS_ROW')

    def check_d2_yes_lov_pattern(self):
        for b in self._row_blocks('UPLOAD_COLUMNS_ROW'):
            cn = (self._get_inner(b, 'COLUMN_NAME') or '').strip().upper()
            ct = (self._get_inner(b, 'COLUMN_TYPE_DSP') or '').strip()
            lq_raw = self._get_inner(b, 'LOV_QUERY_DSP') or ''
            lq = decode_xml_entities(lq_raw)
            if not YES_LOV_PATTERN.search(lq):
                continue
            # conditional Yes LOV (has a WHERE) = delete-column pattern D+1 ("Yes only when the
            # deletable record exists") — the shared Yes LOV can't express that, so it's exempt
            if re.search(r'\bwhere\b', lq, re.I):
                continue
            # Exception: LOVs needing :$column$ or :$flex$ cross-field filters cannot use the
            # shared Yes LOV (which has no bind support). LOV custom is required to host the
            # filter. Examples: a Yes/No column gated by a parent column's value (form locks
            # the field via UI when the parent disallows certain values).
            if ':$column$.' in lq.lower() or ':$flex$.' in lq.lower():
                continue
            ln = (self._get_inner(b, 'LOV_NAME') or '').strip()
            lg = (self._get_inner(b, 'LOV_GUID') or '').strip()
            if ct != 'LOV' or ln != YES_LOV_NAME or lg != YES_LOV_GUID:
                self.add('D2', f'column {cn}: Yes-LOV pattern detected but COLUMN_TYPE_DSP={ct} (expected `LOV`) and/or LOV_NAME={ln!r} (expected `Yes`) — reuse the shared Yes LOV')

    def check_redundant_column_alias_in_sql(self):
        """R33: redundant column aliases in LOV queries / SQL blocks. Pattern:
        `<expr>.<name> <name>,?` where alias matches column name."""
        for tag in ['LOV_QUERY_DSP', 'DEFAULT_VALUE', 'UPLOAD_EXCEL_VALIDATION', 'SQL_TEXT', 'COMMENTS', 'VALUE_TO_ID_QUERY']:
            for b in re.finditer(rf'<{tag}>(.*?)</{tag}>', self.text, flags=re.S):
                sql = decode_xml_entities(b.group(1))
                for line_no, line in enumerate(sql.split('\n')):
                    stripped = line.strip()
                    if not stripped or stripped.startswith('--'):
                        continue
                    m = re.match(r'^([\w\.]+)\.(\w+)\s+(\w+)\s*,?\s*$', stripped)
                    if not m:
                        continue
                    col = m.group(2).lower()
                    alias = m.group(3).lower()
                    if col != alias:
                        continue
                    if alias in ('is', 'as', 'on', 'in', 'or', 'and', 'not', 'then', 'else', 'when', 'where', 'from', 'into', 'loop', 'end'):
                        continue
                    # Locate this in the file via search
                    self.add('R33', f'redundant column alias `{alias}` matches column name in <{tag}> — drop it', search_text=stripped)
                    break   # one violation per block is enough

    def check_use_language_view_in_sql(self):
        """R45b: SQL with `<base>_b` + `<base>_tl` + `language=userenv('lang')` pattern
        should use `<base>_vl` view instead."""
        for tag in ['LOV_QUERY_DSP', 'DEFAULT_VALUE', 'UPLOAD_EXCEL_VALIDATION', 'SQL_TEXT', 'COMMENTS', 'VALUE_TO_ID_QUERY']:
            for b in re.finditer(rf'<{tag}>(.*?)</{tag}>', self.text, flags=re.S):
                sql = decode_xml_entities(b.group(1)).lower()
                # Find table tokens: `<word>_b <alias>` and `<word>_tl <alias>`
                base_tables = set(m.group(1) for m in re.finditer(r'\b(\w+)_b\s+\w+', sql))
                tl_tables = set(m.group(1) for m in re.finditer(r'\b(\w+)_tl\s+\w+', sql))
                common = base_tables & tl_tables
                if not common:
                    continue
                if not re.search(r"\.language\s*=\s*userenv\s*\(\s*'lang'\s*\)", sql):
                    continue
                for base in common:
                    self.add('R45b', f'`{base}_b` + `{base}_tl` + `language=userenv(\'lang\')` pattern in <{tag}> — use `{base}_vl` view instead',
                             search_text=base + '_b')

    def check_lov_reuse(self):
        """L1: heuristic — if a LOV custom column's query fingerprint matches a known
        shared LOV, recommend using the shared LOV."""
        for b in self._row_blocks('UPLOAD_COLUMNS_ROW'):
            ct = (self._get_inner(b, 'COLUMN_TYPE_DSP') or '').strip()
            if ct != 'LOV custom':
                continue
            cn = (self._get_inner(b, 'COLUMN_NAME') or '').strip().upper()
            lq = decode_xml_entities(self._get_inner(b, 'LOV_QUERY_DSP') or '')
            if not lq.strip():
                continue
            if ':$column$.' in lq.lower():
                continue
            for col_pat, qpat, name, guid in SHARED_LOV_FINGERPRINTS:
                if re.match(col_pat, cn) and re.search(qpat, lq, re.IGNORECASE | re.DOTALL):
                    self.add('L1', f'column {cn}: LOV custom matches shared LOV `{name}` ({guid}) — reuse via LOV_NAME + LOV_GUID')
                    break

    def check_upload_mode_parameter(self):
        # Find PARAMETERS_ROW with PARAMETER_NAME like 'Upload Mode'
        for b in self._row_blocks('PARAMETERS_ROW'):
            ptr = self._get_inner(b, 'PARAMETER_TRANSLATIONS') or ''
            names = re.findall(r'<PARAMETER_NAME>([^<]+)</PARAMETER_NAME>', ptr)
            if not any(n.strip().lower() == 'upload mode' for n in names):
                continue
            ln = (self._get_inner(b, 'LOV_NAME') or '').strip()
            lg = (self._get_inner(b, 'LOV_GUID') or '').strip()
            sql = decode_xml_entities(self._get_inner(b, 'SQL_TEXT') or '')
            anchor = decode_xml_entities(self._get_inner(b, 'ANCHOR') or '').strip()
            req = (self._get_inner(b, 'REQUIRED') or '').strip()
            if ln != 'Blitz Upload Mode' or lg != UPLOAD_MODE_LOV_GUID:
                self.add('G1', f'Upload Mode parameter must use shared LOV: LOV_NAME=Blitz Upload Mode + GUID={UPLOAD_MODE_LOV_GUID}')
            # the bind reaches the sql either through a WHERE anchor's SQL_TEXT or by being the anchor itself,
            # which is what an upload whose download SQL references the mode inside an outer joined subquery needs
            if ':p_upload_mode' not in sql.lower() and anchor.lower() != ':p_upload_mode':
                self.add('G2', f'Upload Mode must bind `:p_upload_mode`, either in SQL_TEXT or as the ANCHOR (got SQL_TEXT {sql!r}, ANCHOR {anchor!r})')
            if req != 'Y':
                self.add('G4', f'Upload Mode parameter must have REQUIRED=Y (got: {req!r})')
            return
        self.add('G1', 'Upload Mode parameter not found')

    def check_upload_sqls(self):
        sqls = self._row_blocks('UPLOAD_SQLS_ROW')
        types_seen = {}
        for b in sqls:
            t = (self._get_inner(b, 'SQL_TYPE') or '').strip()
            if t:
                types_seen[t] = b
        # H1: Error SQL row exists with NO SQL_TEXT.
        # Exception: uploads that submit a concurrent program (interface-driven —
        # WIP Mass Load, RVCTP, AR Trx Import, FA Mass Additions Post, etc.) need
        # to read errors from the relevant interface error tables. The framework's
        # auto-generated Error SQL only reads xxen_upload_data.message_, which won't
        # contain those concurrent-program errors. Detect via the Error SQL_TEXT
        # referencing a `*_interface_errors` table.
        if 'Error SQL' not in types_seen:
            self.add('H1', 'UPLOAD_SQLS row of SQL_TYPE=Error SQL not found')
        else:
            txt = self._get_inner(types_seen['Error SQL'], 'SQL_TEXT')
            if txt and txt.strip():
                if not re.search(r'\w+_interface_errors\b', txt, re.IGNORECASE):
                    self.add('H1', 'Error SQL row should have NO SQL_TEXT (auto-generated)')
        # H2: Order By
        if 'Order By' not in types_seen:
            self.add('H2', 'UPLOAD_SQLS row of SQL_TYPE=Order By not found')
        # H3: Success SQL
        if 'Success SQL' not in types_seen:
            self.add('H3', 'UPLOAD_SQLS row of SQL_TYPE=Success SQL not found')

    def check_success_sql_uses_xu_columns(self):
        """H3a / R46: Success SQL must select `xu.action_`, `xu.status_`, `xu.message_`,
        `xu.modified_columns_` as the framework columns — NOT hardcoded codes
        like `'S' status_`, `'C' action_`, or `null message_`. Hardcoded codes
        leak internal codes (S/E/V/C/U/D) into user-facing output instead of the
        translated display value (Success/Error/Valid/Create/Update/Delete)."""
        # Find UPLOAD_SQLS_ROW with SQL_TYPE=Success SQL
        m = re.search(r'<UPLOAD_SQLS_ROW>\s*<SQL_TYPE>Success SQL</SQL_TYPE>\s*<SQL_TEXT>(.*?)</SQL_TEXT>',
                      self.text, flags=re.S | re.IGNORECASE)
        if not m:
            return
        sql = decode_xml_entities(m.group(1))
        first_part = '\n'.join(sql.split('\n')[:40])
        violations = []
        # Hardcoded status_ — user sees raw code (S/V/E/I) instead of translated meaning
        if re.search(r"^\s*'[A-Z]'\s+status_\s*,", first_part, re.MULTILINE):
            violations.append("hardcoded status_ literal (e.g. `'S' status_`) — use `xu.status_` so users see the translated display value")
        # Hardcoded action_
        if re.search(r"^\s*'[A-Z]'\s+action_\s*,", first_part, re.MULTILINE):
            violations.append("hardcoded action_ literal (e.g. `'C' action_`) — use `xu.action_` so users see the translated display value")
        # null message_
        if re.search(r'^\s*null\s+message_\s*,', first_part, re.MULTILINE | re.IGNORECASE):
            violations.append('`null message_` (hardcoded null) — use `xu.message_` so successful rows show the upload procedure\'s message')
        # null modified_columns_
        if re.search(r'^\s*null\s+modified_columns_\s*,', first_part, re.MULTILINE | re.IGNORECASE):
            violations.append('`null modified_columns_` — use `xu.modified_columns_`')
        # Reference status_code_ in display (should only be in WHERE clause)
        # Be conservative: only flag if status_code_ appears as a select column with no expression
        if re.search(r"^\s*xu\.status_code_\s*,", first_part, re.MULTILINE):
            violations.append('`xu.status_code_` exposed as display column — use `xu.status_` (display value), reserve `status_code_` for WHERE filtering')
        if re.search(r"^\s*xu\.action_code_\s*,", first_part, re.MULTILINE):
            violations.append('`xu.action_code_` exposed as display column — use `xu.action_` (display value)')
        for v in violations:
            self.add('H3a', f'Success SQL: {v}', search_text='Success SQL')

    def check_h3b_success_sql_oracle_sourced(self):
        """H3b: Success SQL must re-display stored columns FROM the Oracle tables
        (nvl(oracle, xu)), not be a bare `xu` echo. Heuristic: if the FROM clause
        references only the upload view (no other table), it is a pure echo and can
        never reflect API transformations (upper-cased keys) or derived values."""
        m = re.search(r'<UPLOAD_SQLS_ROW>\s*<SQL_TYPE>Success SQL</SQL_TYPE>\s*<SQL_TEXT>(.*?)</SQL_TEXT>',
                      self.text, flags=re.S | re.I)
        if not m:
            return
        sql = decode_xml_entities(m.group(1)).lower()
        fm = re.search(r'\bfrom\b(.*?)(\bwhere\b|$)', sql, flags=re.S)
        if not fm:
            return
        from_clause = fm.group(1)
        # first token of each FROM part is the table name (split on comma / join)
        tables = []
        for part in re.split(r',|\bjoin\b', from_clause):
            toks = part.strip().split()
            if toks:
                tables.append(toks[0])
        nonview = [t for t in tables if not re.match(r'xxen_\w+_u$', t)]
        if tables and not nonview:
            self.add('H3b',
                     'Success SQL FROM references only the upload view (pure `xu` echo) — re-display stored '
                     'display columns FROM the Oracle tables via `nvl(oracle_table.col, xu.col)` joined by the '
                     'business key (header by upper(document number), line by header_id+line_type+item, descriptors '
                     'by the user value). A bare echo cannot show transformed/derived/stored values.',
                     search_text='Success SQL')

    def check_i5_descriptor_columns_have_default(self):
        """I+5: a read-only descriptor column (name contains DESCRIPTION) must carry a
        DEFAULT_VALUE deriving it from its parent key via :$column$.<parent>, so it
        auto-fills at data entry (and is Oracle-sourced in the Success SQL per H3b).
        Flag read-only, non-hidden description columns with no DEFAULT_VALUE."""
        for b in self._row_blocks('UPLOAD_COLUMNS_ROW'):
            cn = (self._get_inner(b, 'COLUMN_NAME') or '').strip().upper()
            if 'DESCRIPTION' not in cn:
                continue
            read_only = (self._get_inner(b, 'READ_ONLY') or '').strip().upper() == 'Y'
            hidden = (self._get_inner(b, 'HIDDEN') or '').strip().upper() == 'Y'
            has_default = (self._get_inner(b, 'DEFAULT_VALUE') or '').strip() != ''
            if read_only and not hidden and not has_default:
                self.add('I+5', f'column {cn}: read-only descriptor column has no DEFAULT_VALUE — derive it from its '
                                'parent key via :$column$.<parent> so it auto-fills at data entry (and is '
                                'Oracle-sourced in the Success SQL per H3b)',
                         search_text=f'<COLUMN_NAME>{cn}</COLUMN_NAME>')

    def check_no_overrides_on_shared_lov_columns(self):
        """L4: `VALIDATE_FROM_LIST_DSP` / `FILTER_BEFORE_DISPLAY_DSP` may only ever
        hold `Y` (the storage convention is `Y` or null, never `N`).

        These elements are NOT an override even when the row also carries
        LOV_NAME/LOV_GUID: the export deliberately emits the resolved LOV query and
        flags so that a target system on which the shared LOV does not exist still
        imports a self-contained, validating custom LOV. `import_xml_clob` keys off
        that — `nvl2(lov_id,null,<..._dsp>)` — storing NULL when the shared LOV
        resolves and the exported values only when it does not. Flagging their mere
        presence therefore reports the fallback payload as a defect, and removing
        them would delete the fallback. Only `N` is genuinely wrong: on the fallback
        path it would be persisted, breaking the Y/null convention."""
        for tag in ('UPLOAD_COLUMNS_ROW', 'PARAMETERS_ROW'):
            for block in self._row_blocks(tag):
                nm = re.search(r'<COLUMN_NAME>([^<]+)</COLUMN_NAME>', block) or \
                     re.search(r'<PARAMETER_NAME>([^<]+)</PARAMETER_NAME>', block)
                nm = nm.group(1) if nm else '?'
                kind = 'column' if tag == 'UPLOAD_COLUMNS_ROW' else 'parameter'
                for flag in ('VALIDATE_FROM_LIST_DSP', 'FILTER_BEFORE_DISPLAY_DSP'):
                    v = re.search(rf'<{flag}>([^<]*)</{flag}>', block)
                    if v and v.group(1).strip().upper() == 'N':
                        self.add('L4', f'{kind} `{nm}` has `{flag}=N` — `N` is never a valid stored value; the convention is `Y` or null (omit the element).',
                                 search_text=f'<{flag}>N</{flag}>')

    def check_filter_before_display_on_small_lov(self):
        """L3: FILTER_BEFORE_DISPLAY=Y is only for very large LOVs.
        $column$-scoped LOVs are usually small per-row, BUT some EBS master
        tables (items, BOMs, routings, suppliers, customers, parties, GL
        combinations, etc.) can have hundreds of thousands of rows per
        organization at real customers — even when filtered by a $column$
        parent. Only flag $column$-scoped LOVs whose primary table is NOT in
        the known-large EBS list."""
        large_ebs_tables = {
            # Inventory / items / BOM / routing
            'mtl_system_items_b', 'mtl_system_items_vl', 'mtl_system_items_b_kfv',
            'mtl_system_items_kfv', 'mtl_categories_b', 'mtl_categories_vl',
            'mtl_categories_b_kfv', 'mtl_categories_kfv', 'mtl_serial_numbers',
            'mtl_lot_numbers', 'mtl_onhand_quantities_detail',
            'bom_bill_of_materials', 'bom_inventory_components',
            'bom_operational_routings', 'bom_operation_sequences',
            'bom_operation_resources', 'bom_resources',
            'wip_entities', 'wip_discrete_jobs', 'wip_discrete_jobs_v',
            # TCA / parties / customers / suppliers
            'hz_parties', 'hz_cust_accounts', 'hz_cust_account_sites_all',
            'hz_cust_site_uses_all', 'hz_party_sites', 'hz_locations',
            'hz_contact_points', 'hz_relationships',
            'ap_suppliers', 'ap_supplier_sites_all',
            # Transactions
            'po_headers_all', 'po_lines_all', 'po_line_locations_all',
            'po_distributions_all', 'po_requisition_headers_all',
            'po_requisition_lines_all',
            'oe_order_headers_all', 'oe_order_lines_all',
            'ra_customer_trx_all', 'ra_customer_trx_lines_all',
            'ap_invoices_all', 'ap_invoice_lines_all', 'ap_invoice_distributions_all',
            'ap_checks_all', 'ar_cash_receipts_all',
            'rcv_transactions', 'rcv_shipment_headers', 'rcv_shipment_lines',
            'mtl_material_transactions', 'mtl_transaction_accounts',
            'wsh_delivery_details', 'wsh_new_deliveries',
            # Projects / HR / GL
            'pa_projects_all', 'pa_projects', 'pjm_projects_v', 'pjm_project_parameters',
            'pa_tasks', 'pa_expenditure_items_all',
            'per_all_people_f', 'per_all_assignments_f', 'per_people_f',
            'hr_locations_all', 'hr_locations', 'hr_locations_all_vl',
            'gl_code_combinations', 'gl_code_combinations_kfv',
            'gl_je_headers', 'gl_je_lines', 'xla_distribution_links',
            # FA
            'fa_additions_b', 'fa_additions_vl', 'fa_books', 'fa_distribution_history',
            'fa_mass_additions', 'fa_categories_b', 'fa_categories_vl', 'fa_categories_b_kfv',
            # Sales / pricing
            'ra_salesreps_all', 'jtf_rs_salesreps', 'qp_list_headers_all_b',
            'qp_list_headers_b', 'qp_list_lines',
            # Inventory locations / sub-inv
            'mtl_item_locations', 'mtl_item_locations_kfv', 'mtl_secondary_inventories',
        }
        for cm in re.finditer(r'<UPLOAD_COLUMNS_ROW>(.*?)</UPLOAD_COLUMNS_ROW>', self.text, flags=re.S):
            block = cm.group(1)
            if '<FILTER_BEFORE_DISPLAY_DSP>Y</FILTER_BEFORE_DISPLAY_DSP>' not in block:
                continue
            lov_m = re.search(r'<LOV_QUERY_DSP>(.*?)</LOV_QUERY_DSP>', block, flags=re.S)
            if not lov_m:
                continue
            lov = decode_xml_entities(lov_m.group(1))
            # Only flag if $column$-scoped AND LOV does NOT reference any known-large table
            if not re.search(r':\$column\$\.\w+', lov):
                continue
            lov_lower = lov.lower()
            if any(t in lov_lower for t in large_ebs_tables):
                continue
            cn_m = re.search(r'<COLUMN_NAME>([^<]+)</COLUMN_NAME>', block)
            cn = cn_m.group(1) if cn_m else '?'
            self.add('L3', f'column `{cn}` has FILTER_BEFORE_DISPLAY=Y but LOV is :$column$-scoped over a small table. Remove FILTER_BEFORE_DISPLAY_DSP — only set it for LOVs over large tables (items, BOMs, parties, etc., where per-org row counts can reach 100K+).',
                     search_text='<COLUMN_NAME>'+cn+'</COLUMN_NAME>')

    def check_unused_anchors(self):
        """G6: ANCHORS section must not declare anchors that no parameter uses.
        Redundant `2=2` (or higher) anchors clutter the WHERE clause and force
        readers to wonder why they exist."""
        am = re.search(r'<ANCHORS>(.*?)</ANCHORS>', self.text, flags=re.S)
        if not am:
            return
        declared = set(re.findall(r'<ANCHOR>([^<]+)</ANCHOR>', am.group(1)))
        used = set()
        for pm in re.finditer(r'<PARAMETERS_ROW>(.*?)</PARAMETERS_ROW>', self.text, flags=re.S):
            an = re.search(r'<ANCHOR>([^<]+)</ANCHOR>', pm.group(1))
            if an:
                used.add(an.group(1))
        for u in declared - used:
            self.add('G6', f'anchor `{u}` declared in ANCHORS but no parameter uses it — remove it (and remove its `{u}` from the main SQL WHERE clause)',
                     search_text=f'<ANCHOR>{u}</ANCHOR>')

    def check_lov_id_bind_mismatch(self):
        """L2: When a parameter LOV has an `id` column, the framework binds the
        `id` value (numeric or short code) to the SQL_TEXT bind variable — NOT
        the display value. So SQL_TEXT must compare against an id column too,
        not against `_code` / `_name` / `_number` / `_description` columns.
        Heuristic: if LOV has `<expr> id` AND SQL_TEXT pattern is
        `<tbl>.<col>_(code|name|number|description|segments)=:bind` → flag."""
        for pm in re.finditer(r'<PARAMETERS_ROW>(.*?)</PARAMETERS_ROW>', self.text, flags=re.S):
            block = pm.group(1)
            sql_m = re.search(r'<SQL_TEXT>([^<]+)</SQL_TEXT>', block)
            if not sql_m: continue
            sql = decode_xml_entities(sql_m.group(1)).strip()
            lov_m = re.search(r'<LOV_QUERY_DSP>(.*?)</LOV_QUERY_DSP>', block, flags=re.S)
            lov = decode_xml_entities(lov_m.group(1)) if lov_m else ''
            ln_m = re.search(r'<LOV_NAME>([^<]+)</LOV_NAME>', block)
            lov_name = ln_m.group(1).strip() if ln_m else None
            # LOV with id column? Either the LOV_QUERY has it, or it's a known shared LOV with id.
            # Heuristic: `\w+\s+id\s*[,\n]` catches `cg.cost_group_id id,` and `to_number(ml.lookup_code) id,`.
            has_id = bool(re.search(r'\w+\s+id\s*[,\n]', lov))
            # CAVEAT: only add a shared LOV here after empirically verifying with
            #   grep -A 5 '<LOV_NAME>X</LOV_NAME>' content/lovs.xml
            # that its LOV_QUERY contains an `id` column. Most INV/EAM/BOM/GL shared LOVs
            # do NOT have id (verified 2026-06: INV Organization Code, INV Organization Code (all),
            # EAM Asset Group, EAM Asset Number, BOM Department, INV Category, WIP Class Code,
            # GL Ledger — all just `value` + `description`, framework passes display).
            shared_with_id = {'Yes', 'Blitz Upload Mode'}
            # Only promote to shared-LOV id behavior if there's NO LOV_QUERY_DSP override.
            # When the parameter overrides the shared LOV with one that has no id column,
            # the framework binds the display value, not the id.
            if not has_id and lov_m is None and lov_name in shared_with_id:
                has_id = True
            if not has_id:
                continue
            # Look for SQL_TEXT pattern matching display column = bind
            m = re.search(r'(\w+)\.(\w+)\s*=\s*:p_\w+', sql, re.IGNORECASE)
            if not m:
                continue
            col = m.group(2).lower()
            if re.search(r'_(code|name|number|description|segments)$', col):
                pname_m = re.search(r'<PARAMETER_NAME>([^<]+)</PARAMETER_NAME>', block)
                pname = pname_m.group(1).strip() if pname_m else '?'
                self.add('L2', f'parameter `{pname}` bind mismatch: LOV returns `id` but SQL_TEXT compares against display column `{m.group(1)}.{col}` — change SQL_TEXT to use the id column or remove `id` from LOV',
                         search_text=sql_m.group(1)[:50])

    def check_no_apps_initialize_engineatics(self):
        """I8: No `<APPS_INITIALIZE_DATA><USER_NAME>ENGINATICS</USER_NAME>...</APPS_INITIALIZE_DATA>`
        block in agent-authored dev XMLs. Tagging imports with last_updated_by=ENGINATICS
        is the master-export pattern and must not be copy-pasted into new uploads. A file under
        content/ is a master export, which carries the block by design."""
        if 'content' in self.path.resolve().parts:
            return
        m = re.search(r'<APPS_INITIALIZE_DATA>.*?<USER_NAME>\s*ENGINATICS\s*</USER_NAME>.*?</APPS_INITIALIZE_DATA>',
                      self.text, flags=re.S | re.IGNORECASE)
        if m:
            self.add('I8', '<APPS_INITIALIZE_DATA><USER_NAME>ENGINATICS</USER_NAME>...</APPS_INITIALIZE_DATA> block — remove it (Linux import_xml then defaults to ANONYMOUS, which is correct)',
                     search_text='<APPS_INITIALIZE_DATA>')

    def check_p1_parameter_type_present(self):
        """P1: a parameter that is shown to the user (DISPLAY_SEQUENCE not null) must have a
        type. The export omits PARAMETER_TYPE_DSP when the stored parameter_type is null and
        the import stores that null back verbatim, so the hole round-trips forever while the
        setup form hides it. A null type is not a silent `Char`: multiple_values_or_clause
        skips the OR expansion of a `like` parameter because `parameter_type<>'Date'` is NULL,
        and the add-in publishes an empty parameter_type to the client."""
        for block in self._row_blocks('PARAMETERS_ROW'):
            seq = (self._get_inner(block, 'DISPLAY_SEQUENCE') or '').strip()
            if not seq:
                continue
            if (self._get_inner(block, 'PARAMETER_TYPE_DSP') or '').strip():
                continue
            names = re.findall(r'<PARAMETER_NAME>([^<]+)</PARAMETER_NAME>', block)
            name = names[0].strip() if names else '?'
            self.add('P1', f'parameter `{name}` (display_sequence {seq}) has no PARAMETER_TYPE_DSP — '
                           f'add the element (Char/Number/Date/DateTime/LOV/LOV custom/LOV Oracle)',
                     search_text=f'<DISPLAY_SEQUENCE>{seq}</DISPLAY_SEQUENCE>')

    def check_structural_elements(self):
        # I1: GUID
        if not re.search(r'<REPORTS_ROW>.*?<GUID>[A-F0-9]{32}</GUID>', self.text, flags=re.S):
            self.add('I1', 'REPORTS_ROW GUID missing or malformed')
        # I2: REPORT_TRANSLATIONS LANGUAGE=US
        if not re.search(r'<REPORT_TRANSLATIONS_ROW>.*?<LANGUAGE>US</LANGUAGE>.*?<REPORT_NAME>', self.text, flags=re.S):
            self.add('I2', 'REPORT_TRANSLATIONS_ROW for LANGUAGE=US not found')
        # I7: Uploads must assign ONLY at Function level (update-enabled form functions).
        # Corrected 2026-07 to match upload-development.md I7 / the upload-builder skill:
        # uploads MUST ship a Function-level <ASSIGNMENTS> block; a Form/Application/
        # Request-Group grant can expose a data-modifying upload too broadly. (The prior
        # rule forbade all assignments and false-flagged every shipped upload.)
        assignments = re.search(r'<ASSIGNMENTS>(.*?)</ASSIGNMENTS>', self.text, flags=re.S)
        if assignments:
            for row in re.findall(r'<ASSIGNMENTS_ROW>(.*?)</ASSIGNMENTS_ROW>', assignments.group(1), flags=re.S):
                lvl_m = re.search(r'<ASSIGNMENT_LEVEL>\s*(.*?)\s*</ASSIGNMENT_LEVEL>', row)
                lvl = lvl_m.group(1) if lvl_m else ''
                if lvl and lvl != 'Function':
                    self.add('I7', 'upload assignment must be Function level (update-enabled form function), not "%s" — a Form/Application/Request-Group grant can expose a data-modifying upload too broadly' % lvl)

    def run(self, always_on_only=False):
        # Rules that hold for any report definition, upload or not, run before the gate
        self.check_p1_parameter_type_present()
        # Confirm this is an upload XML before running upload-specific rules
        if always_on_only or '<TYPE>U</TYPE>' not in self.text:
            self.violations.sort()
            return self.violations  # not an upload; skip the upload-specific rules
        self.check_a1_framework_columns()
        self.check_a3_sequential_column_numbers()
        self.check_a3t_sequential_template_columns()
        self.check_b7_no_orphan_parameters()
        self.check_d2_yes_lov_pattern()
        self.check_lov_reuse()
        self.check_redundant_column_alias_in_sql()
        self.check_use_language_view_in_sql()
        self.check_upload_mode_parameter()
        self.check_upload_sqls()
        self.check_structural_elements()
        self.check_no_apps_initialize_engineatics()
        self.check_success_sql_uses_xu_columns()
        self.check_h3b_success_sql_oracle_sourced()
        self.check_i5_descriptor_columns_have_default()
        self.check_unused_anchors()
        self.check_lov_id_bind_mismatch()
        self.check_filter_before_display_on_small_lov()
        self.check_no_overrides_on_shared_lov_columns()
        self.violations.sort()
        return self.violations


def main(argv):
    paths = []
    always_on_only = False
    if argv == ['--all-content']:
        # Repo-wide sweep of every content definition, reports included, running only the
        # rules that hold for any report (P1). The upload-specific rules stay out of it:
        # the 11i uploads predate much of the current framework and would drown the output.
        d = REPO_ROOT / 'content'
        paths = sorted(d.rglob('*.xml')) if d.exists() else []
        always_on_only = True
    elif not argv or argv == ['--all']:
        d = REPO_ROOT / 'content' / 'r12' / 'uploads'
        if d.exists():
            paths = sorted(d.glob('*.xml'))
        # Also scan C:/Temp/EAM_build for in-flight uploads
        eam_dir = Path('C:/Temp/EAM_build')
        if eam_dir.exists():
            paths.extend(sorted(eam_dir.glob('EAM_*_Upload.xml')))
    else:
        paths = [Path(a) for a in argv]
    total_violations = 0
    files_with_violations = 0
    for p in paths:
        if not p.exists():
            print(f'NOT FOUND: {p}', file=sys.stderr)
            continue
        l = UploadLint(p)
        v = l.run(always_on_only=always_on_only)
        if not v:
            continue
        files_with_violations += 1
        rel = str(p)
        try:
            rel = str(p.relative_to(REPO_ROOT)).replace('\\', '/')
        except ValueError:
            pass
        for ln, rid, msg in v:
            print(f'{rel}:{ln} {rid} - {msg}')
            total_violations += 1
    if total_violations:
        print(f'\n{total_violations} violation(s) across {files_with_violations} file(s)', file=sys.stderr)
        return 1
    print(f'OK: lint clean across {len(paths)} file(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
