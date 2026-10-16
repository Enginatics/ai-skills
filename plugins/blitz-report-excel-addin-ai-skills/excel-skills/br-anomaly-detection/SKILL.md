---
name: br-anomaly-detection
description: Find unusual or suspicious rows in a Blitz Report dataset — outlier transactions, duplicate invoices, abnormal amounts, data-quality errors — using robust statistics, Mahalanobis distance, Benford's Law, and duplicate detection. Use this whenever the user wants to detect anomalies, outliers, exceptions, "things that look wrong", duplicate or suspicious invoices, fraud signals, or data-quality issues in an Oracle EBS / Blitz Report sheet. Trigger it for "flag anything unusual", "find outliers", "check for duplicates", or "what looks suspicious here", even without a named method.
---

# br-anomaly-detection — flag the rows that don't belong

> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Surface the rows in a Blitz Report that deviate from the norm and explain **why** each was
flagged, so a person can review them. Everything is computed in the Office.js script inside the
workbook — no data leaves the sheet. Favour **explainable, deterministic** methods: an AP clerk or
auditor must be able to see the reason, not just a black-box score.

## When to use / not use
- **Use** for: outlier/exception detection, duplicate-invoice scans, abnormal-amount checks,
  data-quality auditing, fraud *screening* (candidates for review).
- **Don't use** for: predicting a labelled outcome (classification), or normal grouping
  (`br-clustering`). Don't use the word "fraud" as a conclusion — these are rows that **warrant
  review**, not proof of anything.

## Shared conventions (the br_ analytics house style)
1. **Source** = an existing Blitz Report sheet; row 1 is headers. **Never add, rename, or delete
   source columns** — read only.
2. **Scratch work** on a helper sheet `br_calc_`; delete it when done.
3. **Outputs (all four):** a results sheet `br_anomaly_results` (key + metric(s) + score + `Flag` +
   `Reason`); a chart; a dashboard (reuse `br-data-dashboard` via `read_skill("br-data-dashboard")`
   for its KPI/slicer layout; add a slicer on `Flag`); a plain-English chat summary with
   recommended follow-up.
4. **Determinism:** the methods below are deterministic by design — same input, same flags. State
   the threshold you used and why.
5. **Privacy:** operate only on the provided sheet.

## Workflow — follow in order

### Step 1 — Locate the data and decide what "unusual" means
Read headers + 5-10 rows (`get_cell_ranges`). Identify the **key column** (Invoice, Vendor,
Transaction) and the **metric column(s)**. Then pick the method from the user's intent — ask only if
genuinely ambiguous:
- one numeric metric, "find outliers in Amount" → **robust z-score + IQR** (Step 2a)
- several numeric metrics, "rows that are odd across columns" → **Mahalanobis distance** (Step 2b)
- "are these amounts manipulated / too many round numbers" → **Benford's Law** (Step 2c)
- "find duplicate / near-duplicate invoices" → **duplicate scan** (Step 2d)

You can run more than one (e.g. robust z **and** a duplicate scan) and combine the reasons.

### Step 2 — Score + write results sheet (implementations in `references/methods.md`)  *(single `execute_office_js` call)*
In one call: read the key + metric column(s), run the chosen method(s) below, build the
flagged-row array sorted by score descending, create `br_anomaly_results`, and write all rows
(headers + key + metric(s) + `Score` + `Flag` + `Reason`). Do not issue a separate read call and
then a separate write call; do not insert any verification read between the score and the write.

**2a. Robust z-score (median + MAD) and IQR.** Use the **median and MAD, not mean and standard
deviation** — a few big outliers inflate the mean/sd and hide themselves. Flag rows with
modified-z `> 3.5` (and/or beyond the 1.5×IQR fences). The reason reads like "4.1× MAD above median
on Amount".

**2b. Mahalanobis distance.** Standardise the numeric columns, compute the covariance and its
inverse, and score each row by Mahalanobis distance; flag rows beyond the chi-square cutoff for the
number of features (e.g. p < 0.01). Reason: "multivariate outlier, p<0.01".

**2c. Benford's Law.** Compare the observed first-digit distribution of the amounts against Benford's
expected curve with a chi-square test; flag the digits that are over-represented and the rows behind
them. Only valid on naturally-spanning amounts over many rows (see gotchas).

**2d. Duplicate / near-duplicate scan.** Group by the keys that should be unique together (e.g.
Vendor + Amount), and within a group flag rows whose dates fall within a small window (e.g. ≤ 5
days) or that share an invoice number. Reason: "possible duplicate of INV-00123 (same vendor +
amount, 2 days apart)".

### Step 3 — Results sheet (written in Step 2's call)
`br_anomaly_results` holds: key column(s) + the metric(s) + an anomaly `Score` + a `Flag`
(Yes/No) + a human-readable `Reason`, with flagged rows sorted to the top. This sheet is created
and populated **inside the Step 2 `execute_office_js` call** — not as a separate write.

### Step 4 — Chart  *(single `execute_office_js` call — the permitted separate charts call)*
- For 2a/2b: a **sorted score bar** with a horizontal **threshold line**, or a 2-D scatter with
  flagged points highlighted.
- For 2c: a bar of **observed vs expected** first-digit frequencies.

### Step 5 — Dashboard
Build the dashboard from `br_anomaly_results` with a **slicer on `Flag`** so the user can
isolate the exceptions and see their total value/count.

### Step 6 — Chat summary
Report: the method(s) and threshold, how many rows were flagged (and what share of total value they
represent), the **top offenders with their reasons**, and the recommended next step ("send these to
AP for review", "the Benford spike on leading-9 amounts is worth a closer look", "the noise rows may
be a data-quality issue"). Frame flags as candidates for review, never as proven fraud.

## Gotchas
- Mean/standard-deviation outlier tests are self-defeating — outliers inflate both. Use median + MAD.
- Mahalanobis needs more rows than features and a non-degenerate covariance; if columns are
  collinear, drop one or fall back to per-column robust z.
- Benford only applies to amounts that span several orders of magnitude and arise naturally; it is
  **invalid** on assigned numbers, capped ranges, or small samples (rule of thumb: ≥ ~300 rows).
- Negative amounts / credits: decide whether to test absolute values or treat credits separately.
- Never assert fraud. Flags are rows that warrant human review.
