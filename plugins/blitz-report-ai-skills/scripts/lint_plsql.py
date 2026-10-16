#!/usr/bin/env python
"""Lint a PL/SQL package source file (.pks or .pkb) against the project's
coding-standards.md rules. Exit code 0 = clean, non-zero = violations found.

Usage:
  python tools/lint_plsql.py [path1.pkb path2.pks ...]
  python tools/lint_plsql.py --all   # scan sql/ + sql/extensions/

Each violation is reported as:
  <file>:<line> RULE <id> - <message>

Rules currently checked (all have a stable ID matching coding-standards.md):
  R7    Two blank lines before AND after each top-level procedure (body only).
  R34   No `!=` outside string literals — use `<>`.
  R39a  No `andy_log` calls (debug-only, breaks on customer instances).
  R7-spec Single blank line between procedure declarations in the spec.
  R9    No spaces around assignment / comparison operators.
  R31a  Multi-table FROM clauses inside cursor SELECTs must put each table on
        its own line (basic check).
  R55   Every Oracle identifier must be <=30 bytes (procedure/function names,
        DDL object names) — over-30 compiles on 19c dev but fails on 11.2/12.1
        customers with PLS-00114 / ORA-00972.
  R56   No PL/SQL record type constructors (qualified expressions) — an 18c-only
        feature that compiles on 19c dev but fails on pre-18c customers with
        PLS-00222. Assign record fields individually instead.
  R57   Scripts that run BEFORE create_objects.sql (sql/upgrade_pre.sql) must
        reference custom xxen_ objects only through execute immediate, owner
        qualified. A static reference fails to compile at a first installation
        (ORA-00942) and kills the WHOLE anonymous block, silently.

Future rules can be added with a corresponding ID — keep IDs stable so
violations can be referenced in commit messages and grep-able.
"""
import os, re, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Scripts executed BEFORE sql/create_objects.sql by scripts/install.sh, i.e. while the
# custom xxen_ objects may not exist yet. Rule R57 applies to exactly these files.
PRE_CREATE_OBJECTS_SCRIPTS = ('upgrade_pre.sql',)

class Lint:
    def __init__(self, path: Path):
        self.path = path
        self.text = path.read_text(encoding='utf-8', errors='replace')
        self.lines = self.text.replace('\r\n', '\n').split('\n')
        self.is_body = path.suffix.lower() == '.pkb'
        self.violations = []          # (line_no_1based, rule_id, message)
        self._mask = self._build_string_comment_mask()

    def _build_string_comment_mask(self):
        """Return a list (one per line) of strings where each char is:
          ' ' = code, '"' = inside SQL string literal, '#' = inside line comment,
          '/' = inside block comment.
        Used to skip violations inside strings/comments.
        """
        mask = []
        in_block = False
        for line in self.lines:
            row = []
            i = 0
            in_str = False
            line_comment = False
            while i < len(line):
                c = line[i]
                if in_block:
                    row.append('/')
                    if c == '*' and i+1 < len(line) and line[i+1] == '/':
                        row.append('/')
                        in_block = False
                        i += 2
                        continue
                    i += 1
                    continue
                if line_comment:
                    row.append('#')
                    i += 1
                    continue
                if in_str:
                    row.append('"')
                    if c == "'":
                        if i+1 < len(line) and line[i+1] == "'":
                            row.append('"')
                            i += 2
                            continue
                        in_str = False
                    i += 1
                    continue
                if c == '-' and i+1 < len(line) and line[i+1] == '-':
                    line_comment = True
                    row.append('#')
                    i += 1
                    continue
                if c == '/' and i+1 < len(line) and line[i+1] == '*':
                    in_block = True
                    row.append('/')
                    i += 1
                    continue
                if c == "'":
                    in_str = True
                    row.append('"')
                    i += 1
                    continue
                row.append(' ')
                i += 1
            mask.append(''.join(row))
        return mask

    def _is_code_at(self, line_idx, col):
        m = self._mask[line_idx] if line_idx < len(self._mask) else ''
        if col >= len(m): return False
        return m[col] == ' '

    def add(self, line_no_1based, rule_id, message):
        self.violations.append((line_no_1based, rule_id, message))

    # ---- Rule implementations ----

    def _find_top_level_procedure_starts(self):
        """Find indexes of procedures/functions declared at the package's
        top level, i.e. NOT nested inside another procedure's declare section.
        Tracks nesting via a NAME STACK (only matching `end <proc_name>;`
        decrements). Lines like `end if;`, `end loop;`, `end case;` are NOT
        procedure-ends and don't affect the stack."""
        starts = []
        stack = []          # stack of open procedure/function names
        package_body_seen = False
        package_name = None
        for i, line in enumerate(self.lines):
            if not package_body_seen:
                m = re.match(r'^create\s+(?:or\s+replace\s+)?package\s+body\s+(\w+)', line, re.IGNORECASE)
                if m:
                    package_body_seen = True
                    package_name = m.group(1).lower()
                continue
            # Procedure/function definition (not forward declaration — must end with `is`/`as`
            # OR have parameters and not end with `;` on the same line).
            # Heuristic: `procedure foo(...);` on one line = forward decl. We rely on the
            # fact that EAM packages have implementations only.
            m = re.match(r'^\s*(procedure|function)\s+(\w+)', line, re.IGNORECASE)
            if m:
                # Skip clear forward declarations: stripped line ends with `;` AND has no `is` or `as`
                stripped = line.strip().rstrip()
                if stripped.endswith(';') and not re.search(r'\bis\s*$|\bas\s*$', stripped, re.IGNORECASE):
                    continue
                proc_name = m.group(2).lower()
                if not stack:
                    starts.append(i)
                stack.append(proc_name)
                continue
            # Procedure end: `end <proc_name>;` matching the top of the stack
            m = re.match(r'^\s*end\s+(\w+)\s*;', line, re.IGNORECASE)
            if m and stack:
                ending = m.group(1).lower()
                if ending == stack[-1]:
                    stack.pop()
                # else: probably `end if` / `end loop` / `end case` — ignore
                continue
        return starts

    def check_no_blank_after_procedure_is(self):
        """R7b: No blank lines between `procedure/function X is` (or `... ) is`)
        and the first declaration / begin. Applies to ALL procedures and
        functions, not just top-level."""
        for i, line in enumerate(self.lines):
            # Match `procedure X ... is` or `function X ... return T is`
            # The `is` keyword must end the declaration. Could be on a
            # multi-line signature where `is` is the last token.
            stripped = line.rstrip()
            if not re.search(r'\bis\s*$', stripped, re.IGNORECASE):
                continue
            # Confirm this line is part of a procedure/function declaration
            # by walking backwards to find the keyword
            j = i
            found_kw = False
            while j >= 0 and j > i - 100:
                if re.match(r'^\s*(procedure|function)\s+\w+', self.lines[j], re.IGNORECASE):
                    found_kw = True
                    break
                if self.lines[j].strip() == '':
                    break
                j -= 1
            if not found_kw:
                continue
            # Count blank lines immediately after this `... is` line
            blanks = 0
            k = i + 1
            while k < len(self.lines) and self.lines[k].strip() == '':
                blanks += 1
                k += 1
            if blanks > 0:
                proc_match = re.match(r'^\s*(procedure|function)\s+(\w+)', self.lines[j], re.IGNORECASE)
                proc_name = proc_match.group(2) if proc_match else '?'
                self.add(i+1, 'R7b', f'no blank lines allowed between `{proc_match.group(1) if proc_match else "procedure"} {proc_name} ... is` and first declaration/`begin` (got {blanks})')

    def check_top_level_procedure_blank_lines(self):
        """R7: Two blank lines BEFORE AND AFTER each top-level procedure
        (package body only). Single blank line between spec declarations."""
        proc_starts = self._find_top_level_procedure_starts() if self.is_body else []
        # In .pks files there are usually only declarations (no body). Different rule.
        if self.path.suffix.lower() == '.pks':
            for i, line in enumerate(self.lines):
                if re.match(r'^\s*procedure\s+\w+', line) or re.match(r'^\s*function\s+\w+', line):
                    # In spec: previous non-blank should have at most 1 blank line gap
                    j = i - 1
                    blanks = 0
                    while j >= 0 and self.lines[j].strip() == '':
                        blanks += 1; j -= 1
                    if j < 0:  # at top of declarations is fine
                        continue
                    # Allow 1 blank between declarations
                    if blanks > 1:
                        self.add(i+1, 'R7-spec', f'expected single blank line between spec declarations, got {blanks}')
            return
        # Body file: enforce exactly 2 blanks before each top-level procedure
        for idx in proc_starts:
            j = idx - 1
            blanks = 0
            while j >= 0 and self.lines[j].strip() == '':
                blanks += 1; j -= 1
            if j < 0:
                continue   # very first thing in file is a procedure (unusual but OK)
            if blanks != 2:
                proc_match = re.match(r'^\s*(?:procedure|function)\s+(\w+)', self.lines[idx], re.IGNORECASE)
                proc_name = proc_match.group(1) if proc_match else '?'
                self.add(idx+1, 'R7', f'expected 2 blank lines before top-level procedure `{proc_name}`, got {blanks}')
        # Final `end <pkg>;` should also have 2 blanks before it
        for i, line in enumerate(self.lines):
            m = re.match(r'^end\s+(\w+)\s*;', line)
            if m and any(re.match(r'^create\s+or\s+replace\s+package\s+body\s+'+m.group(1), self.lines[k], re.IGNORECASE)
                          for k in range(0, i)):
                j = i - 1
                blanks = 0
                while j >= 0 and self.lines[j].strip() == '':
                    blanks += 1; j -= 1
                if blanks != 2 and j >= 0:
                    self.add(i+1, 'R7', f'expected 2 blank lines before `end {m.group(1)};`, got {blanks}')
                break

    def check_no_inequality_operator(self):
        """R34: Use `<>` not `!=` (in SQL/PL/SQL code, outside strings/comments)."""
        for li, line in enumerate(self.lines):
            for m in re.finditer(r'!=', line):
                if self._is_code_at(li, m.start()):
                    self.add(li+1, 'R34', 'use `<>` not `!=`')
                    break

    def check_no_andy_log(self):
        """R39a: andy_log is dev-only; remove before commit."""
        for li, line in enumerate(self.lines):
            for m in re.finditer(r'\bandy_log\b', line, re.IGNORECASE):
                if self._is_code_at(li, m.start()):
                    self.add(li+1, 'R39a', 'andy_log is dev-only — remove before commit')
                    break

    def check_no_spaces_around_operators(self):
        """R9: No spaces around `:=` `=` `<>` `<=` `>=` `<` `>` in code.
        Heuristic — only flag clear violations like `x := y` (with both sides
        having spaces) to avoid false positives on `where x = 1`-style legit SQL.
        We flag: `:=` with space on either side; `<>` with space on either side."""
        for li, line in enumerate(self.lines):
            # `:=` with surrounding spaces
            for m in re.finditer(r'(\s:=|:=\s)', line):
                if self._is_code_at(li, m.start()):
                    self.add(li+1, 'R9', 'no spaces around `:=` (assignment)')
                    break
            else:
                continue
            break

    def check_redundant_column_alias(self):
        """R33: A column alias that exactly matches the column name is redundant.
        Detects patterns like `tbl.foo foo,` or `tbl.foo foo` (end of select list).
        Skips function expressions, case-when, parenthesized expressions, strings.
        Heuristic: only fires when the line is of shape `<expr>.<name> <name>,?`
        where the trailing alias equals the rightmost qualified column name."""
        # Process inside SELECT clauses only — narrow scope. We approximate by
        # looking for lines that end with `<word>.<word> <word>[,]?` at top level.
        for li, line in enumerate(self.lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('--'):
                continue
            # Match lines like `prefix.column_name column_name,` or `prefix.column_name column_name`
            # The rightmost `.<word>` followed by space and the same word, optional comma.
            m = re.match(r'^([\w\.]+)\.(\w+)\s+(\w+)\s*,?\s*$', stripped)
            if not m:
                continue
            col = m.group(2).lower()
            alias = m.group(3).lower()
            if col != alias:
                continue
            # PL/SQL keywords that can appear in this position — skip
            if alias in ('is', 'as', 'on', 'in', 'or', 'and', 'not', 'then', 'else', 'when', 'where', 'from', 'into', 'loop', 'end'):
                continue
            # Confirm it's at top-level (not inside string/comment)
            indent_col = len(line) - len(stripped)
            if not self._is_code_at(li, indent_col):
                continue
            self.add(li+1, 'R33', f'redundant column alias `{alias}` matches column name — drop it')

    def check_use_language_view(self):
        """R45b: When the FROM clause has both `<base>_b` and `<base>_tl` AND a
        `<base>_tl.language=userenv('lang')` filter, prefer `<base>_vl` instead.
        Detects the pattern across multi-line FROM clauses inside a single SQL
        block (delimited by SELECT...FROM...WHERE...next-clause)."""
        # Walk the file looking for FROM clauses; gather table tokens; then scan
        # ahead in the WHERE clause for the language-userenv pattern.
        text = '\n'.join(self.lines)
        # Find each `from` keyword at code position (skip in strings/comments — heuristic via mask)
        # For each, capture the from-list tokens until next clause keyword (where/group/order/connect/start/union/having)
        # Then check the where-clause for the language filter
        from_pat = re.compile(r'\bfrom\b', re.IGNORECASE)
        next_clause_pat = re.compile(r'\b(where|group\s+by|order\s+by|having|connect\s+by|start\s+with|union(\s+all)?|minus|intersect)\b', re.IGNORECASE)
        for fm in from_pat.finditer(text):
            # Crude location-to-line mapping
            start_line = text.count('\n', 0, fm.start())
            # Skip if inside string/comment per mask
            col = fm.start() - (text.rfind('\n', 0, fm.start()) + 1)
            if start_line < len(self._mask) and col < len(self._mask[start_line]) and self._mask[start_line][col] != ' ':
                continue
            # Find next clause keyword
            nxt = next_clause_pat.search(text, fm.end())
            if not nxt:
                continue
            from_clause = text[fm.end():nxt.start()]
            # Extract table names: <schema>.<name> <alias> or <name> <alias>
            tables = re.findall(r'\b(\w+)\b\s+\w+\s*[,\)\s]', from_clause)
            base_tables = set()
            tl_tables = set()
            for t in tables:
                tl = t.lower()
                if tl.endswith('_tl'):
                    tl_tables.add(tl[:-3])
                elif tl.endswith('_b'):
                    base_tables.add(tl[:-2])
            common = base_tables & tl_tables
            if not common:
                continue
            # Check the WHERE clause (text after the next-clause keyword if it was where) for language=userenv('lang')
            # Just look ahead 2000 chars
            tail = text[nxt.start():nxt.start()+2000]
            if not re.search(r"\.language\s*=\s*userenv\s*\(\s*'lang'\s*\)", tail, re.IGNORECASE):
                continue
            # Report at the FROM line
            for base in common:
                self.add(start_line+1, 'R45b', f'`{base}_b` + `{base}_tl` + `language=userenv(\'lang\')` pattern — use `{base}_vl` view instead')

    def _enclosing_routine_body(self, li):
        """Source of the innermost routine containing line li (nearest preceding
        procedure/function whose matching `end <name>;` is at/after li), or None when li is not
        inside any routine. Handles the flat-declare style where nested routines also start at
        column 0."""
        j = li
        while j >= 0:
            m = re.match(r'^(?:procedure|function)\s+(\w+)', self.lines[j])
            if m:
                name = m.group(1)
                for k in range(j + 1, len(self.lines)):
                    if re.match(r'^end\s+' + re.escape(name) + r'\s*;', self.lines[k], re.IGNORECASE):
                        if k >= li:
                            return '\n'.join(self.lines[j:k + 1])
                        break
            j -= 1
        return None

    def _routine_touches_upload_data(self, li):
        """R45 intent: only dynamic SQL that reads/updates the upload data is a violation. True
        when the enclosing routine (or the whole package, for a package-level construct) references
        an upload-data signal - the base table xxen_upload_data, the deterministic upload view
        (xxen_..._u), or its framework columns. A helper that builds dynamic SQL over other tables
        touches none of these and returns False."""
        body = self._enclosing_routine_body(li)
        if body is None:
            body = '\n'.join(self.lines)
        b = body.lower()
        if 'xxen_upload_data' in b or 'status_code_' in b or 'upload_rowid' in b or 'modified_columns_' in b:
            return True
        return re.search(r'\bxxen_\w+_u\b', b) is not None

    def check_no_dynamic_sql_in_upload_packages(self):
        """R45: In upload packages (xxen_*_upload) the upload view name is deterministic from
        the report's GUID, so reading/updating the upload data must use STATIC SQL. Dynamic SQL is
        flagged ONLY when the enclosing routine actually reads/manipulates the upload data (it
        references xxen_upload_data, the upload view xxen_..._u, or its framework columns
        status_code_/upload_rowid/modified_columns_); standalone helpers that build dynamic SQL
        over other tables are not the target. Flag:
          - `open <var> for <var>;`  (ref cursor with a string variable)
          - `execute immediate <var>` (NOT `execute immediate '<literal>'`)
          - declarations like `type <name> is ref cursor`
        Only applies to package bodies whose name matches `xxen_*_upload`."""
        # Detect package name from `create or replace package body`
        pkg_name = None
        for line in self.lines:
            m = re.match(r'^create\s+(?:or\s+replace\s+)?package\s+body\s+(\w+)', line, re.IGNORECASE)
            if m:
                pkg_name = m.group(1).lower()
                break
        if not pkg_name:
            return
        if not re.match(r'^xxen_.*_upload$', pkg_name):
            return
        for li, line in enumerate(self.lines):
            stripped = line.strip()
            if not stripped:
                continue
            # `execute immediate VAR` — flag if next token after EXECUTE IMMEDIATE is a variable (not a literal)
            m = re.match(r'^execute\s+immediate\s+([^\'\s;]+)', stripped, re.IGNORECASE)
            if m:
                token = m.group(1)
                # Allow `execute immediate '...'` (literal SQL) and `execute immediate 'literal'||VAR` (rare)
                if not token.startswith("'"):
                    if self._is_code_at(li, line.index('execute', 0) if 'execute' in line else 0) and self._routine_touches_upload_data(li):
                        self.add(li+1, 'R45', f'`execute immediate {token}` in upload package — static SQL preferred (view name is deterministic, see upload-development.md)')
                        continue
            # `open <var> for <var>;` — open ref cursor for a variable
            m = re.match(r'^open\s+(\w+)\s+for\s+(\w+)\s*;\s*$', stripped, re.IGNORECASE)
            if m and self._routine_touches_upload_data(li):
                # Allow `open <var> for select ...` (inline static SQL) — different match pattern
                self.add(li+1, 'R45', f'`open {m.group(1)} for {m.group(2)};` (ref cursor on string variable) — use `for c in (select ...) loop` with inline SELECT instead')
                continue
            # `type <name> is ref cursor` declarations
            m = re.match(r'^type\s+(\w+)\s+is\s+ref\s+cursor', stripped, re.IGNORECASE)
            if m and self._routine_touches_upload_data(li):
                self.add(li+1, 'R45', f'`type {m.group(1)} is ref cursor` — upload packages should not use ref cursors')
                continue
            # `cursor <name> is` declarations — inline `for c in (select ...) loop` is preferred
            # so reviewers see the SQL where it executes (no scrolling back to a separate declaration).
            # Exception: a cursor reused across multiple for-loops is OK.
            m = re.match(r'^cursor\s+(\w+)\s+is\b', stripped, re.IGNORECASE)
            if m:
                cursor_name = m.group(1)
                # Count `for c in <cursor_name> loop` usages
                usage_pat = re.compile(r'\bfor\s+\w+\s+in\s+' + cursor_name + r'\s+loop\b', re.IGNORECASE)
                usage_count = sum(1 for ll in self.lines if usage_pat.search(ll))
                if usage_count <= 1:
                    self.add(li+1, 'R45', f'separate cursor declaration `{cursor_name}` — inline the SELECT in `for c in (select ...) loop` so reviewers see the SQL where it executes (only justify a separate cursor if it is reused across multiple loops)')
                continue

    def check_connector_at_end_of_line(self):
        """R44: When multi-condition expressions wrap, `and`/`or` connectors go
        at the END of the previous line, never at the START of a new line.
        Applies to PL/SQL `if`/`while`/`exit when` AND SQL `where`/`having`/`on`."""
        for li, line in enumerate(self.lines):
            stripped = line.lstrip()
            # Match leading `and ` or `or ` (with at least one space or paren after)
            m = re.match(r'^(and|or)\s+\S', stripped, re.IGNORECASE)
            if not m:
                continue
            # Must be at top level of the current line (not inside a string or comment)
            indent_col = len(line) - len(stripped)
            if not self._is_code_at(li, indent_col):
                continue
            # Find first non-blank prior line — for context (not used to validate)
            j = li - 1
            while j >= 0 and self.lines[j].strip() == '':
                j -= 1
            if j < 0:
                continue
            connector = m.group(1).lower()
            self.add(li+1, 'R44', f'`{connector}` at start of line — move to end of previous line')

    def check_cursor_for_indent(self):
        """R29: For multi-line cursor `for X in (...)`, the SQL body inside the
        parens must be indented to the same column as `for`. (See
        coding-standards.md rule #29.)"""
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            m = re.match(r'^(\s*)(for\s+\w+\s+in\s*\()', line, re.IGNORECASE)
            if not m:
                i += 1; continue
            for_indent = len(m.group(1))
            # Walk forward tracking paren depth from the `(`
            paren_pos = line.index('(', m.end(2)-1)
            depth = 1   # counted the opening paren
            j = i
            col = paren_pos + 1
            cursor_lines = []           # (line_idx, line) of multi-line body
            while j < len(self.lines) and depth > 0:
                cur = self.lines[j]
                start_col = col if j == i else 0
                # Update depth based on chars from start_col to end-of-line, ignoring strings/comments
                mask_line = self._mask[j] if j < len(self._mask) else ''
                k = start_col
                while k < len(cur) and depth > 0:
                    ch = cur[k]
                    is_code = (k < len(mask_line) and mask_line[k] == ' ')
                    if is_code:
                        if ch == '(':
                            depth += 1
                        elif ch == ')':
                            depth -= 1
                            if depth == 0:
                                break
                    k += 1
                if depth == 0:
                    # multi-line iff there were lines beyond the `for` line before close
                    break
                # next line is part of the cursor body
                j += 1
                col = 0
                if j < len(self.lines):
                    cursor_lines.append((j, self.lines[j]))
            # Single-line cursor: skip
            if not cursor_lines:
                i += 1
                continue
            # Check indent of each non-blank body line. Skip the closing `) loop` line
            # (the line where depth returned to 0). cursor_lines is everything between
            # `for c in (` line and the closing line.
            for li, body_line in cursor_lines:
                if not body_line.strip():
                    continue
                # The closing-paren line will be in cursor_lines if body wraps.
                # Don't flag the line that contains the matching `)`.
                if re.match(r'^\s*\)', body_line):
                    continue
                body_indent = len(body_line) - len(body_line.lstrip(' '))
                if body_indent != for_indent:
                    self.add(li+1, 'R29', f'cursor body indent ({body_indent}) does not match `for` indent ({for_indent})')
                    break   # one violation per cursor is enough
            i = j + 1

    def check_cursor_select_formatting(self):
        """R31a: Multi-table FROM in a cursor SELECT must put each table on
        its own line. Heuristic: find `for X in (` blocks, then look for
        `from <tbl>, <tbl>` or `from <tbl>,<tbl>` on a single line."""
        # Find blocks `for \w+ in (` and the matching `)`
        # Simple heuristic: scan for `^\s*from\s+\w+.*,.*\w+` lines INSIDE a
        # for-cursor block
        in_cursor = False
        depth = 0
        cursor_start_line = -1
        for li, line in enumerate(self.lines):
            stripped = line.strip()
            if not in_cursor and re.search(r'\bfor\s+\w+\s+in\s*\(', line):
                in_cursor = True
                cursor_start_line = li
                # Count parens on this line
                depth = line.count('(') - line.count(')')
                continue
            if in_cursor:
                depth += line.count('(') - line.count(')')
                # Inside cursor — look for multi-table FROM
                m = re.match(r'^\s*from\s+\S.*,', line, re.IGNORECASE)
                if m:
                    # Check there's no newline before next comma — lazy heuristic:
                    # if line contains `from X, Y` (comma after a non-empty token)
                    if re.search(r'\bfrom\s+\w[\w\s\.]*,\s*\w', line, re.IGNORECASE):
                        self.add(li+1, 'R31a', 'multi-table FROM in cursor SELECT — put each table on its own line')
                # Look for compact SELECT: `select a, b, c` on one line
                if re.match(r'^\s*select\s+\w[\w\s\.]*,\s*\w', line, re.IGNORECASE):
                    if not re.search(r'select\s*$', line.lower()):
                        self.add(li+1, 'R31a', 'multi-column SELECT in cursor — put each column on its own line')
                if depth <= 0:
                    in_cursor = False
                    depth = 0

    def check_identifier_length_30(self):
        """R55: Oracle identifiers must be <=30 bytes. An over-30 procedure/function
        name or DDL object name compiles fine on 19c dev (128-byte limit) but fails
        on 11.2/12.1 customers (PLS-00114 for PL/SQL, ORA-00972 for DDL — the object
        is then silently not created / the package is dropped). Checks the two classes
        that have actually broken customer installs; skips matches inside strings/comments.
        See coding-standards.md #55."""
        # class 1 — procedure/function definitions (and forward decls): `procedure NAME` / `function NAME`
        def_re = re.compile(r'\b(procedure|function)\s+([A-Za-z0-9_#$]+)', re.IGNORECASE)
        # class 2 — DDL object names: `create [or replace] [global temporary] [unique] <kind> [schema.]NAME`
        ddl_re = re.compile(
            r'\bcreate\s+(?:or\s+replace\s+)?(?:global\s+temporary\s+)?(?:unique\s+)?'
            r'(table|index|sequence|view|materialized\s+view|type|synonym|trigger)\s+'
            r'(?:"?[A-Za-z0-9_#$]+"?\.)?"?([A-Za-z0-9_#$]+)"?',
            re.IGNORECASE)
        for li, line in enumerate(self.lines):
            for m in def_re.finditer(line):
                if not self._is_code_at(li, m.start()):
                    continue
                name = m.group(2)
                if len(name) > 30:
                    self.add(li+1, 'R55', f'{m.group(1).lower()} name `{name}` is {len(name)} bytes (>30) - rename to <=30; over-30 fails on 11.2/12.1 with PLS-00114')
            for m in ddl_re.finditer(line):
                if not self._is_code_at(li, m.start()):
                    continue
                name = m.group(2)
                if len(name) > 30:
                    self.add(li+1, 'R55', f'{re.sub(r"\\s+"," ",m.group(1).lower())} name `{name}` is {len(name)} bytes (>30) - rename to <=30; over-30 fails on 11.2/12.1 with ORA-00972')

    def check_no_record_type_constructor(self):
        """R56: PL/SQL record type constructors (qualified expressions, e.g.
        `g_job_rec_tbl(i):=g_job_rec_type(a,b,c);`) are an 18c-only feature.
        They compile on the 19c dev instances but fail on pre-18c customer
        databases (11.2/12.1) with PLS-00222 and get the package dropped.
        Assign the record fields individually instead. Detects record types
        DECLARED IN THE SAME FILE that are used call-style; object types
        (create type ... as object) have real constructors and are fine.
        Shipped bug: XXEN_WIP_UPLOAD g_job_rec_type(...) broke the package on
        12.1.0.2 and 11.2.0.4 databases."""
        rec_types = set()
        decl_re = re.compile(r'\btype\s+(\w+)\s+is\s+record\b', re.IGNORECASE)
        for li, line in enumerate(self.lines):
            for m in decl_re.finditer(line):
                if self._is_code_at(li, m.start()):
                    rec_types.add(m.group(1).lower())
        if not rec_types:
            return
        use_re = re.compile(r'(?<![\w.$])(' + '|'.join(re.escape(r) for r in rec_types) + r')\s*\(', re.IGNORECASE)
        for li, line in enumerate(self.lines):
            for m in use_re.finditer(line):
                if not self._is_code_at(li, m.start()):
                    continue
                # skip the declaration itself and type references (`type X is record (`, `table of X(`, `%`, `X%type`)
                prefix = line[:m.start()]
                if re.search(r'\b(type|of)\s*$', prefix, re.IGNORECASE):
                    continue
                self.add(li+1, 'R56', f'record type constructor `{m.group(1)}(...)` is 18c-only (PLS-00222 on pre-18c customers) - assign the record fields individually')

    def _multiline_code_mask(self):
        """Like _build_string_comment_mask but tracks string literals and block comments
        ACROSS lines. Required for the standalone install/upgrade scripts, whose
        `execute immediate '` payloads routinely span dozens of lines - the per-line mask
        would read every one of those lines as code. Returns one string per line where
        ' ' = code and any other character = string/comment."""
        if getattr(self, '_ml_mask', None) is not None:
            return self._ml_mask
        mask = []
        in_str = False
        in_block = False
        for line in self.lines:
            row = []
            i = 0
            in_line_comment = False
            while i < len(line):
                c = line[i]
                if in_line_comment:
                    row.append('#'); i += 1
                elif in_block:
                    if c == '*' and i + 1 < len(line) and line[i+1] == '/':
                        row.append('/'); row.append('/'); i += 2; in_block = False
                    else:
                        row.append('/'); i += 1
                elif in_str:
                    if c == "'":
                        if i + 1 < len(line) and line[i+1] == "'":
                            row.append('"'); row.append('"'); i += 2
                        else:
                            row.append('"'); i += 1; in_str = False
                    else:
                        row.append('"'); i += 1
                else:
                    if c == "'":
                        row.append('"'); i += 1; in_str = True
                    elif c == '-' and i + 1 < len(line) and line[i+1] == '-':
                        row.append('#'); row.append('#'); i += 2; in_line_comment = True
                    elif c == '/' and i + 1 < len(line) and line[i+1] == '*':
                        row.append('/'); row.append('/'); i += 2; in_block = True
                    else:
                        row.append(' '); i += 1
            mask.append(''.join(row))
        self._ml_mask = mask
        return mask

    def check_no_static_custom_object_in_pre_script(self):
        """R57 - upgrade_pre.sql runs as ONE anonymous block before create_objects.sql,
        so a static xxen_ reference fails to compile at a first installation and the
        whole script is skipped, silently. Every custom object must go through execute
        immediate, owner qualified. Uses the multi-line mask: references inside the
        execute immediate payload and inside quoted dictionary lookups ('XXEN_REPORTS')
        are string literals, so only genuine static references are reported."""
        if self.path.name.lower() not in PRE_CREATE_OBJECTS_SCRIPTS:
            return
        mask = self._multiline_code_mask()
        for li, line in enumerate(self.lines):
            row = mask[li]
            for m in re.finditer(r'\bxxen_\w+', line, re.IGNORECASE):
                if m.start() >= len(row) or row[m.start()] != ' ':
                    continue
                self.add(li+1, 'R57', 'static reference to custom object `%s` - %s runs before create_objects.sql, so this fails to compile with ORA-00942 at a first installation and the whole block is skipped; wrap it in execute immediate and qualify it with the owner' % (m.group(0), self.path.name))

    def run(self):
        self.check_top_level_procedure_blank_lines()
        self.check_identifier_length_30()
        self.check_no_record_type_constructor()
        self.check_no_static_custom_object_in_pre_script()
        if self.is_body:
            self.check_no_blank_after_procedure_is()
        self.check_no_inequality_operator()
        self.check_no_andy_log()
        self.check_no_spaces_around_operators()
        if self.is_body:
            self.check_cursor_for_indent()
            self.check_cursor_select_formatting()
            self.check_connector_at_end_of_line()
            self.check_no_dynamic_sql_in_upload_packages()
            self.check_redundant_column_alias()
            self.check_use_language_view()
        self.violations.sort()
        return self.violations


def lint_file(path: Path):
    l = Lint(path)
    return l.run()


def main(argv):
    paths = []
    if not argv or argv == ['--all']:
        for sub in ('sql', 'sql/extensions'):
            d = REPO_ROOT / sub
            if d.exists():
                for p in d.iterdir():
                    if p.suffix.lower() in ('.pks', '.pkb'):
                        paths.append(p)
        for name in PRE_CREATE_OBJECTS_SCRIPTS:
            p = REPO_ROOT / 'sql' / name
            if p.exists():
                paths.append(p)
    else:
        paths = [Path(a) for a in argv]
    total_violations = 0
    for p in paths:
        if not p.exists():
            print(f'NOT FOUND: {p}', file=sys.stderr)
            continue
        v = lint_file(p)
        if not v:
            continue
        rel = str(p.relative_to(REPO_ROOT)) if p.is_absolute() and REPO_ROOT in p.parents else str(p)
        rel = rel.replace('\\', '/')
        for ln, rid, msg in v:
            print(f'{rel}:{ln} {rid} - {msg}')
            total_violations += 1
    if total_violations:
        print(f'\n{total_violations} violation(s) across {len([p for p in paths if lint_file(p)])} file(s)', file=sys.stderr)
        return 1
    print(f'OK: lint clean across {len(paths)} file(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
