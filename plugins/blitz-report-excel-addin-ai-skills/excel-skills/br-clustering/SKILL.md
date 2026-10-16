---
name: br-clustering
description: Segment a Blitz Report dataset into natural groups using K-Means or DBSCAN, then profile and name each segment in plain business language. Use this whenever the user wants to cluster, segment, or group rows of an Oracle EBS / Blitz Report sheet — e.g. "segment our customers", "group these vendors by spend behaviour", "find natural clusters in this data", "which items behave alike", or any request to discover groupings the data isn't already labelled with. Trigger it even when the user says "segment" or "group" without naming an algorithm.
---

# br_clustering — segment a Blitz Report dataset

> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Discover the natural groups inside a tabular Blitz Report (customers, vendors, items, GL
accounts, employees…) and translate each group into something a business user can act on.
You handle feature selection, the algorithm, and — most importantly — the *interpretation*;
the Office.js script handles the maths inside the workbook so no data leaves the sheet.

## When to use / not use
- **Use** for: "segment", "cluster", "group", "find natural groupings", "which of these behave
  alike", customer/vendor/item/account segmentation, persona discovery.
- **Don't use** for: a simple pivot/group-by the user already knows the categories for (that's a
  pivot, not clustering), single-column ranking (use `br_abc_pareto`), or labelled prediction
  (that's classification, not clustering).

## Shared conventions (the br_ analytics house style)
These apply to every `br_` analytics skill:
1. **Source** = an existing Blitz Report data sheet. Row 1 is headers. **Never add, rename, or
   delete the source columns** — read only.
2. **Scratch work** goes on a helper sheet named `br_calc_`; delete it when finished so the
   workbook stays clean.
3. **Outputs (all four):**
   - a results sheet `br_clustering_results` (key column(s) + the computed label, joined back),
   - a chart on that sheet,
   - a dashboard view (reuse the `br-data-dashboard` skill — call `read_skill("br-data-dashboard")`
     for its KPI/slicer/chart layout; add a slicer on the new label column),
   - a plain-English chat summary with recommended business actions.
4. **Determinism:** fix the random seed (e.g. 42) and state every parameter you chose and *why*,
   so a re-run reproduces and the user can audit the choice.
5. **Privacy:** operate only on the provided sheet; never send row-level data outside the workbook.

## Workflow — follow in order

### Step 1 — Locate and read the source sheet
If the user named a sheet, use it; otherwise use the active sheet (the deliverable a Blitz Report
left visible). Read headers + 5-10 rows with `get_cell_ranges` to understand the shape. Identify:
- a **key column** that names each row (Customer, Vendor, Item, Account) — kept verbatim in output,
- the **numeric feature columns** to cluster on (Amount, Qty, Days, Count, Balance…).

### Step 2 — Select and prepare features
Clustering is distance-based, so preparation decides the result more than the algorithm does.
- Keep numeric columns that describe *behaviour* (spend, frequency, recency, balance, lead time).
- **Drop identifiers** (IDs, codes, phone numbers) — clustering on an ID number is meaningless.
- Handle missing values: impute numeric blanks with the column median; drop a column that is
  mostly blank.
- **Standardise** every feature to mean 0 / sd 1 (z-score). This is non-negotiable: without it a
  column measured in millions (revenue) drowns out a column measured in days. See
  `references/algorithms.md` for the scaler.
- If the user insists on a categorical driver, one-hot encode it; otherwise stay numeric.

### Step 3 — Pick the algorithm
- **K-Means** when the user wants a *set number of segments* and groups are roughly blob-shaped
  (the usual customer/vendor/item case). Fast, every row gets a cluster.
- **DBSCAN** when groups have *irregular shape/density* or the user also wants **outliers flagged**
  — DBSCAN labels sparse rows as noise (`-1`), which doubles as a light outlier finder.
- If unsure, default to **K-Means** and mention DBSCAN as the density/outlier alternative.

### Step 4 — Fit + write results + profile  *(single `execute_office_js` call)*
In one call: read the standardised feature columns, fit the chosen algorithm (sweeping `k` as
below), assign each row its `Cluster` label, write the `br_clustering_results` sheet (Step 5), and
build the cluster profile table (Step 6) — all in the same JS block. Trust the values this call
returns; do not insert a verification read between fitting, writing, and profiling.

**K-Means — choosing `k` carefully (this is where it's easy to go wrong):**
- If the user gave a target number of segments (e.g. "give me 4 tiers"), **use that `k`** — they
  usually have a business reason. Still report the quality so they know how clean it is.
- Otherwise, sweep `k = 2..8` and look at **both** inertia (the elbow) **and** silhouette. **Do not
  just take the highest silhouette** — silhouette tends to reward the *fewest, broadest* clusters
  and will happily merge real segments. Prefer the `k` at the **elbow** (where inertia stops
  dropping sharply); use silhouette as a tie-breaker and a quality read-out, not the sole judge.
  *Worked example:* on a 3-behaviour dataset, silhouette peaked at k=2 (0.62) but inertia fell
  278→115 from k=2→3 with silhouette still strong at k=3 (0.57) — the elbow at **k=3** is the
  correct, business-meaningful answer; k=2 would have hidden a segment.
- **Always show the user the sweep** (k, silhouette, inertia) and the `k` you picked, so they can
  override. Report silhouette honestly: ≈ >0.5 strong, 0.25-0.5 moderate, <0.25 weak.
Implementation in `references/algorithms.md`.

**DBSCAN:** set `min_samples ≈ 2 × (#features)`; estimate `eps` from the k-distance heuristic
(the "knee" of sorted nearest-neighbour distances) in `references/algorithms.md`. Report how many
rows fell into noise.

### Step 5 — Write the results sheet (written in Step 4's call)
`br_clustering_results` holds: the key column(s) + the original features + a `Cluster` column
(and `IsNoise` for DBSCAN). This is written **inside the Step 4 `execute_office_js` call**, in the
same block that computed the labels — never as a separate write, and on a new sheet (never write
back onto the source).

### Step 6 — Profile and NAME each cluster (the part that delivers value; table built in Step 4's call)
A cluster number means nothing to a business user. Build a **cluster profile table**: for each
cluster, the row count, % of total, and the mean of each feature (in original units, not scaled).
Then give each cluster a business name from its profile, e.g. *"High-value, frequent — 8% of
customers, 41% of revenue"* or *"Dormant low-spend — large count, tiny value"*. This naming is the
skill's main output; spend effort here.

### Step 7 — Charts  *(single `execute_office_js` call — the permitted separate charts call)*
On `br_clustering_results`:
- a **2-D scatter** coloured by cluster, plotted on the two highest-variance scaled features (label
  the axes with the real column names so it's readable),
- a **cluster-size bar** (count per cluster).

### Step 8 — Dashboard
Build the dashboard via the `br-data-dashboard` conventions, sourced from
`br_clustering_results`, with a **slicer on `Cluster`** so the user can drill into one segment and
watch the KPIs (count, total value, average) update.

### Step 9 — Chat summary
Report: the algorithm and why, `k`/`eps` chosen and the quality metric, each cluster's name + size
+ defining traits, and **2-3 recommended actions** ("focus retention on the dormant-high-value
segment; the noise rows are worth a data-quality check"). End with where the sheet and dashboard are.

## Gotchas
- Forgetting to standardise → one big-magnitude column dictates every cluster. Always scale.
- Clustering on ID/code columns → nonsense. Exclude them in Step 2.
- Reporting a cluster number without a name/profile → the user can't act on it. Step 6 is mandatory.
- Over-reading weak clusters: if silhouette is low, say the data may not segment cleanly rather than
  inventing personas.
- K-Means is seed-sensitive — fix the seed and use k-means++ init (see references).
