---
name: br-cash-working-capital
description: >
  Orchestrate a full Oracle EBS cash & working-capital review in Excel: run the duplicate-payment
  recovery, AR collections worklist, and AP payment-run optimizer, cross-check the open duplicate
  invoices against the recommended pay-run (so you don't pay a duplicate you're about to claw back),
  then assemble one master scorecard with the total cash opportunity by lever (recover / protect /
  capture discounts / collect / DPO headroom), a combined net-cash-by-week view, and the ranked
  cross-lever action list. Use when the user asks for a working-capital review, "where's our cash",
  free up / find cash, a cash opportunities pack, or a combined AP/AR cash position.
# Trigger: Slash command + auto
---

# Cash & Working-Capital Orchestrator (br-cash-working-capital)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 20 minutes (chained orchestration).

Assemble a single cash & working-capital scorecard across three levers. You drive the sequence, the
cross-lever cross-check, and the master roll-up; each lever's own skill (or its primary report) does
the detail. Run steps in order, keeping every lever's sheets.

**Requires:** br-run-reports, br-data-dashboard, and the lever skills
br-ap-duplicate-payments, br-ar-collections-worklist, br-ap-payment-optimizer.

## Division of responsibility — READ FIRST
- **You do NOT run Blitz reports yourself** — extraction is always via **br-run-reports** (directly,
  or inside the lever skills). Never call `br_*` functions; never touch a result sheet until its run
  is confirmed complete.
- **Delegate one lever at a time and wait for it to finish before starting the next.** The runs are
  asynchronous; overlapping them stalls them.
- **Robust hand-off:** invoke each lever skill to produce its sheets. **If a lever skill does not
  fire** (composition can be unreliable), fall back to running that lever's **primary** report
  directly via br-run-reports and scoring it inline with the same rules. Never skip a lever silently —
  show it as "not assessed" if neither path worked.
- **Read-and-recommend only:** nothing here executes a fix (no hold, no supplier claim, no payment
  batch, no dunning send, no credit hold). It quantifies the opportunity and recommends the sequence;
  a human executes each step.

## When to use
"Working-capital review", "where's our cash / how do we free up cash", "cash opportunities pack",
"combined AP/AR cash position", a treasurer/controller cash review. For a single lever, use that
lever's skill directly.

## Inputs (collect up front)
- **Operating Unit** (required) — used by all three levers. (AR Aging takes Reporting Level +
  Reporting Context: set Reporting Level = `Operating Unit`, Reporting Context = the OU; AP reports
  take Operating Unit directly. The lever skills handle their own param shape.) Ledger optional.
- **As-of Date** (AR aging snapshot; default today).
- **Pay Through Date** (the AP pay-run horizon; default = end of the current month).
- *Optional:* **Cash available** (drives the optimizer's constrained pay-run AND the combined
  net-cash view); duplicate **lookback** (default 24 months); materiality thresholds; cost-of-cash
  rate (default 10%).

## CONFIG

### Lever → skill → primary report (fallback if the skill doesn't fire)
Each lever skill runs its own reports **directly by name** (no broad discovery search). If a lever
skill doesn't fire and you run its fallback report yourself, pass the **documented name + params
below directly** — do NOT `br_report_list_external`-search first; only fall back to a search on
`#BLITZ_REPORT_NOT_FOUND`.

| Lever | Skill | Fallback primary report (+ key params, r12-verified) |
|---|---|---|
| **Recover / protect cash** (duplicates) | br-ap-duplicate-payments | `AP Invoices and Lines` — Operating Unit + Invoice Date From/To (lookback) + **Display Level = Headers** |
| **Collect** (AR) | br-ar-collections-worklist | `AR Aging` — Reporting Level = `Operating Unit` + Reporting Context = OU + As Of Date |
| **Capture / defer** (AP pay run) | br-ap-payment-optimizer | `AP Cash Requirement` — Operating Unit + Pay Through Date |

### Cash-opportunity roll-up (the master metrics)
From each lever's own returned figures:
- **Recover now** = duplicate **Recoverable $** (cash back from suppliers — true new cash).
- **Protect now** = duplicate **Preventable $** (open duplicate invoices to hold before they pay).
- **Capture this week** = optimizer **discount $ capturable** (Capture-Discount total — true new cash).
- **Collect** = collections **collectible past-due $** (the worklist's prioritized at-risk total —
  this is cash *timing*, not new cash; label it so).
- **DPO headroom** = optimizer **Defer-To-Due $** (cash you can legitimately keep longer).
- **Total cash opportunity (hard)** = Recover now + Capture this week (the two unambiguous new-cash
  levers). Show Protect / Collect / DPO as separate timing/risk levers — do NOT add them into the
  hard number (they're prevention, timing, and headroom, not realized cash).

### 🚨 Cross-check (the orchestration centerpiece — only the orchestrator can do this)
Join the duplicate skill's **Preventable** pairs (open duplicate invoices) against the optimizer's
**recommended pay-run** (`Pay_Schedule`) on **`INVOICE_ID`** — both `AP Invoices and Lines` and
`AP Cash Requirement` expose it, so it's an exact match (do NOT join on supplier number: the pay-run
carries the supplier as `TRADING_PARTNER` *name*, not a number; fall back to
`TRADING_PARTNER`+`INVOICE_NUM` only if an `INVOICE_ID` is somehow missing).
**🚨 Use the EXACT `INVOICE_ID` join — the duplicate lever's Preventable list MUST carry the real
`INVOICE_ID` values (see br-ap-duplicate-payments Step 3: `INVOICE_ID` A/B, not a row index).** If you
find yourself joining on invoice number, you dropped the id upstream — go back and carry it. A pure
`INVOICE_NUM`-only fallback is a **false-positive magnet** (a real bug seen in a run: invoice number
`"1"` matched a junk pay-run row → a bogus RED match): if you ever must fall back, require
`TRADING_PARTNER`+`INVOICE_NUM` **and skip degenerate invoice numbers** (length ≤ 2, all-zero, or pure
`"1"`/`"2"`) — never RED-flag on `INVOICE_NUM` alone.
**Canonical JS — COPY VERBATIM** (ports of `tools/skill_tests/skill_logic.py::cross_check_by_id`
and `::cross_check_plausible`):
```js
function crossCheckById(preventablePairs, payRun) {
  const ids = new Set(payRun.map(p => String(p.invoiceId)));   // exact INVOICE_ID join
  return preventablePairs.filter(pr =>
    ids.has(String(pr.invoiceIdA)) || ids.has(String(pr.invoiceIdB)));
}
// Gate the RED set on the PAY-RUN size, NOT the preventable count: preventable
// invoices are open, and open invoices are what the pay-run contains, so
// RED/preventable is ~100% (normal). > ~10% of the PAY-RUN = systematic -> "review".
const crossCheckPlausible = (redCount, payRunCount, maxRate = 0.10) =>
  !payRunCount ? true : (redCount / payRunCount) <= maxRate;
```
**Any match = an open duplicate the pay-run is about to pay** → flag it **RED**: pull it from the run
and hold it. This is the single highest-value insight of the pack — a duplicate you'd otherwise pay
*this week* and then have to claw back. Report each match with supplier, both invoice numbers, $, and
the pay-by date it was scheduled for.

**🚨 The cross-check inherits the duplicate lever's guards — it cannot launder a false positive into a
headline.** The Preventable list you join MUST already have the **same-amount cluster guard** applied
(ERS / auto-invoicing groups of ≥3 demoted) and its **$ rolled up by distinct invoice**, not per pair.
If you skip those upstream, the cross-check faithfully amplifies the noise: a live run reported
**"1,316 RED matches, $120.9M about to be paid twice"** that was entirely ERS same-amount clusters
(invoice numbers `ERS-13578-224817` etc.), ~36% of the AP universe — the join key was right, the
*input* was garbage. So: (1) the RED **$ is the distinct-invoice sum**, never the per-pair exposure
added up; and (2) **apply the plausibility gate against the RIGHT denominator** — `RED ÷ pay-run count`,
**NOT** `RED ÷ preventable count`. Preventable invoices are **open**, and open invoices are exactly what
the pay-run contains, so **nearly every preventable pair WILL appear in the pay-run** (`RED/preventable`
is ~90–100% and is **normal, not a trigger**). A live run mis-gated on `RED/preventable = 84/89 = 94%`
and falsely declared "systematic" when `RED/pay-run = 84/4061 = 2%` was perfectly plausible. Use
`cross_check_plausible(redCount, payRunCount)`: only when RED exceeds ~10% **of the pay-run** is the
duplicate lever surfacing a systematic pattern → present "high volume — likely ERS/recurring, review
before holding", NOT a confident "$X about to be paid twice". A real about-to-pay-a-duplicate set is a
handful of invoices, not thousands. (And if the cross-check still shows many ERS pairs, the duplicate
lever skipped its ERS-vs-ERS guard upstream — fix it there, not with an ad-hoc split here.)

**🚨 A "0 RED / CLEAN" result is only trustworthy if the two `INVOICE_ID` sets can actually join —
validate the join key before reporting CLEAN.** A live run reported a false **"CLEAN"** because the
duplicate lever handed over **worksheet row indices** (`3, 4, 5, …`) instead of real `INVOICE_ID`s,
while the pay-run carried real Oracle ids (`242901, …`) — different id spaces, so the join matched
nothing **by construction**. Before trusting a zero/low result, sanity-check: **Preventable invoices
are OPEN (unpaid) — they are exactly what an AP Cash Requirement pay-run contains — so if you flagged
N preventable invoices and ZERO appear in the pay-run, the join key is broken, NOT clean.** Confirm the
two id sets are the same kind of value (both large Oracle ids; ranges overlap) — if they're disjoint
in magnitude (one set is small sequential integers ≈ the dup universe size, the other is large ids),
**report "cross-check could not run — INVOICE_ID mismatch, the duplicate lever must carry the real
Invoice Id (its far-right column), not a row index", NOT "CLEAN".**

### Overall status
- **Action needed** — any cross-check RED match, OR hard cash opportunity above a material threshold.
- **Opportunity** — discounts/recoverables found but none colliding with the pay-run.
- **Clean** — no duplicates, no capturable discounts, no material past-due.

### Output sheets & tab order (left to right)
`Cash_Working_Capital` (master, first), then `AP_Dup_Recovery`, `AR_Collections`, `AP_Pay_Run`
(the lever dashboards), then each lever's detail sheets after them.

## Pipeline
1. **Levers, in sequence — DELEGATE one at a time, wait for each.**
   a. **br-ap-duplicate-payments** (Operating Unit + lookback) → `AP_Dup_Recovery` + `Dup_Candidates`.
      Capture Recoverable $, Preventable $, and the **open Preventable invoice list** for the cross-check.
   b. **br-ar-collections-worklist** (OU + As-of Date) → `AR_Collections` + `Worklist`. Capture
      collectible past-due $ and the top accounts.
   c. **br-ap-payment-optimizer** (OU + Pay Through Date + cash cap) → `AP_Pay_Run` + `Pay_Schedule`.
      Capture discount $ capturable, Defer-To-Due $, recommended pay-run $, and the **pay-run invoice
      list** for the cross-check.
   On a no-fire, run that lever's fallback report and score inline with the same rules; capture the
   same figures from the values the sub-skill returned in its **own final JS call** — do **not** insert
   extra `get_cell_ranges` reads against a lever's sheet between invocations (br-analytics-standards
   Rule 8). Trust the sub-skill return values.
2. **Cross-check *(single `execute_office_js` call)*.** This is a genuine barrier — it needs BOTH the
   Preventable list (1a) and the pay-run (1c). In one call: join them per the CONFIG rule and build the
   `Cross_Check` warning set (RED matches). Return the match count and $. (If either lever didn't
   produce its list, skip with a noted caveat — never fail the pack.)
3. **Master scorecard *(single `execute_office_js` call)*** (delegate to br-data-dashboard if it fires;
   else build inline). On a NEW `Cash_Working_Capital` sheet at **position 0**, in one call: the
   headline **Total cash opportunity (hard)** band; the **per-lever** rows (Recover / Protect /
   Capture / Collect / DPO headroom — each with $, the source lever, and the recommended action); the
   **cross-check RED panel** (the about-to-pay-a-duplicate matches, top of the actions); and, when a
   cash figure is available, a **net-cash-by-week** mini-view (AR collectible inflow vs the pay-run
   outflow across the horizon). Every KPI is a formula referencing the lever dashboards/details
   (COUNTIFS/SUMIFS) so it refreshes when a lever is re-run. Read the per-lever figures from the values
   each sub-skill returned in its final JS call — do **not** insert `get_cell_ranges` reads against the
   lever sheets here (Rule 8). Any charts go in a **second** `execute_office_js` call.
   - **Build mechanics (house standard):** build the master on a NEW sheet at position 0; leave every
     lever's own sheet untouched and **do NOT rename** it (the master links by name). **Do NOT use a
     multi-row `copyToRange`** to fill the per-lever rows (it can latch onto the wrong source box and
     duplicate headers) — write each row's formula explicitly. After building, scan **beyond** the
     dashboard's column range, clear stray cells, and widen amount columns so values don't render as
     `######`.
4. **Action narrative *(single `set_cell_range` call)*.** Write all ≤6 ranked bullets on
   `Cash_Working_Capital` in one call, ordered by speed-to-cash: (1) any cross-check RED — hold these
   before the pay-run; (2) claw back the biggest Recoverable duplicate; (3) capture this week's
   discounts ($ + the pay-by date); (4) chase the top collectible accounts; (5) the DPO headroom you
   can keep; (6) the single biggest data-quality fix (e.g. a duplicate vendor master). Do not call
   `set_cell_range` once per bullet.
5. **Arrange tabs + final validation *(single `execute_office_js` call + one read)*.** Reorder tabs
   per CONFIG and make `Cash_Working_Capital` active — only after the master exists. Then the **one
   permitted verification read**: confirm each lever's $ on the master ties to that lever's own
   dashboard, and that every cross-check RED match exists on both `Dup_Candidates` and `Pay_Schedule`.

## Validation
- Every lever appears on the master with its $ (or an explicit "not assessed").
- Per-lever figures on the master tie to that lever's own sheet.
- The hard total = Recover now + Capture this week only (Protect / Collect / DPO are shown separately,
  never folded into the hard number).
- Every cross-check RED match is present in **both** the Preventable list and the pay-run.

## Closed-loop (roadmap, not executed here)
Each fix is a separate human-approved step: hold an open/preventable duplicate (Blitz Upload), raise a
supplier credit/refund (manual), build the payment run (Payment Process Request), send dunning
(external), set a credit hold (customer-profile upload). This orchestrator quantifies and sequences;
a human executes.
