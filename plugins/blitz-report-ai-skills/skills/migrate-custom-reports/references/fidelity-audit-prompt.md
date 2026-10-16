# Independent fidelity audit: agent prompt

Give this prompt to a second agent (a subagent, or Codex with `codex exec`) before the first delivery of a converted report. The second agent must not see the converter's reasoning, only the files. Fill in the two paths.

---

READ-ONLY AUDIT. Do not edit or create any file, do not connect to any database, do not propose rewritten code.

Original program files: `<gather folder of the program>`: the `_rdf.xml` or `.rex`, the data template, the RTF layout, the custom package bodies and the `.ldt`. Converted Blitz Report: `<report XML>`. The SQL is the first `<SQL_TEXT>` after `<GUID>`. Each `<PARAMETERS_ROW>`'s `<SQL_TEXT>` is injected at its anchor (`1=1`, `2=2`, `&lexical`); a `:bind` is bound directly.

Enumerate EVERY value or row rule the original produces that reaches the printed output (an RTF field, a paper-layout field, an element the package writes), including everything it computes outside its main query:
- formula columns (`CF_`), and placeholders (`CP_`) assigned inside formulas;
- summaries (`CS_`) that a formula or the layout reads;
- format triggers that return FALSE, and group filters, including one on a parent group that suppresses its linked child queries;
- BeforeReport and AfterParameterForm triggers that build lexicals or derive binds;
- BI Publisher data triggers, group filters and element expressions;
- for a PL/SQL program, every variable its loop writes to the output.

A cursor column selected as a literal (`0 basic`, `null source`) is a placeholder the loop fills later. Check every branch of a `union`, and the `union` versus `union all` key.

For each item give:
- **Item:** the name and the output field it feeds.
- **Original:** what it computes, `file:line`, the essential code quoted briefly.
- **Blitz:** the equivalent, `file:line` in the XML, or `none`.
- **Verdict:** OK (same result), DIFFERENT (computed differently: say how), or MISSING.
- **Consequence:** what the user sees for DIFFERENT or MISSING, such as a blank column, zero amount, wrong sign, rows shown that should be hidden, or a wrong filter.

Check the edge behaviour too:
- what the original prints when a lookup finds no row or several;
- declared widths and number precision;
- `nvl` defaults and `valueIfNull`;
- dates printed as text;
- row order and row grain;
- serial numbers and running totals;
- report modes;
- parameters: what an empty optional parameter does to rows whose filtered column is null (`col=nvl(:p,col)` drops them), a value equal to an `nvl()` stand-in, a free-text value set that is upper case only, the exact date boundaries, which id or value each list passes;
- name capture in PL/SQL cursors: a predicate that compares a column with an identifier that is both a column of the queried view and a procedure parameter.

Ignore pure layout: fonts, page headers, the run date and parameter echo lines.

Output: markdown, a table `Item | Original (file:line) | Blitz (file:line) | Verdict | Consequence` listing every output-relevant item, OK ones briefly. End with `<report>: N items, X DIFFERENT, Y MISSING`. If unsure whether two expressions are equivalent, say DIFFERENT and state what would need to be checked.

---

## Fix brief, when a round of corrections is delegated

Give the fixing agent the audit's table and these working rules:
- Start from the currently delivered definition, not an older file.
- Correct each DIFFERENT and MISSING item to what the original prints. Re-check each item against the source first. If the audit is wrong, say so and leave the item.
- Work in its own folder: the build script, the resulting XML, and a NOTES.md with one row per item: FIXED with how and the proof, NOT FIXED with why, or AUDIT WRONG.
- Pass the value fidelity gate (`value-fidelity.md`) on the result, including the full-fetch cost, before reporting.
- No commits, no DML or DDL on shared instances; prefix every uploaded file with the report id.
