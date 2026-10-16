---
name: br-gl-account-coder
description: >
  Suggest GL account coding from the ledger's own history: given transactions to code (or re-code),
  mine GL Account Analysis for how this entity has historically coded the same supplier, source,
  category or description, and propose the account combination with a confidence level and the
  precedent shown. Optionally stage approved corrections as a journal via the GL Journal Upload —
  only on explicit user confirmation. Use when the user asks "which account should this go to",
  wants miscoding candidates found, or needs a reclass journal drafted. Recommend-first; WRITES to
  Oracle EBS only via the gated journal step.
# Trigger: Slash command + auto
---

# GL Account Coding Assistant (br-gl-account-coder)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.

> **Performance:** read `br-analytics-standards` at the start of every run. For the optional journal
> step, **read `br-run-uploads` FIRST**.

## When to use
"What account does this belong to", "find likely miscodings in period X", "draft the reclass
journal for these", "how do we normally code invoices from supplier Y". This is a COMPANION to the
accountant, not an auto-coder: every suggestion shows its precedent, and nothing posts without a
human.

## Inputs
- **Ledger** (required) and **Period / date range** for the history mine — ask if not supplied.
- **What to code** — rows the user supplies (a pasted list, another report's output) OR a scope to
  scan for miscoding candidates (an account, a source, a supplier).

## Reports and uploads used (authoritative names — do NOT broad-search for them)
| Name | Type | Role |
|---|---|---|
| `GL Account Analysis` | Report | the history mine — account combinations by source, category, description and subledger detail |
| `GL Journals` | Report | journal-level context when a candidate needs its origin checked |
| `GL Journal Upload` | Upload | **write path** — the staged reclass/correction journal |

Pass the exact names; fall back to a search only on `#BLITZ_REPORT_NOT_FOUND`.

## Workflow
1. **Mine the history**: run `GL Account Analysis` for the ledger/period scope (restrict by source
   or account range where the user gave one — never wide open, per br-run-reports).
2. **Build the precedent table** in-sheet: for each (supplier / source / category / normalized
   description keyword) → the account combinations historically used, with frequency and recency.
3. **Suggest**: for each row to code, the best-precedent combination with a confidence class —
   **STRONG** (one dominant precedent, ≥90% of history), **SPLIT** (two+ combinations in real use —
   show both and the discriminator, e.g. "freight goes to 5230 for org A but 5240 for org B"),
   **NONE** (no usable precedent — say so; never invent an account). Show the precedent rows that
   justify each suggestion.
4. **Miscoding scan mode**: rows whose coded account contradicts a STRONG precedent are flagged as
   candidates, ranked by amount, with the precedent shown. These are candidates for review — never
   assert "wrong", the precedent may be the thing that changed.
5. **Stage the journal (optional, gated)**: only when the user explicitly approves specific
   corrections — build the reclass in the `GL Journal Upload` grid (balanced Dr/Cr per line, the
   user's period and category), validate, show journal totals and line count, submit only on a
   second explicit confirmation. The journal still routes through the customer's normal GL
   approval/posting flow — say that.

## Hard rules
- **Never suggest an account with no precedent in this ledger's own history.** No generic chart-of-
  accounts knowledge substitutes for the entity's actual practice.
- **Cross-validated combinations only**: a suggested combination must exist in history — never
  compose a novel segment mix.
- Confidence comes from precedent counts, not from the model's certainty.

## Degradation rules
- Thin history for the scope → say the mine is thin and widen the period only with the user's OK.
- Cost-center-dependent codings (SPLIT class) that the user cannot discriminate → leave uncoded
  with both options shown, never pick silently.

## Talk in the user's language
"Post a reclass journal of $84,300 across 12 lines to period MAY-26?" — accounts, amounts,
periods; never `br_*` functions or helper sheets.
