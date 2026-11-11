---
name: ebs-performance-review
description: Server-wide Oracle EBS performance review for a customer from Blitz Report DBA extracts. Covers memory and parameter configuration, the top AWR SQLs, and literal-SQL hard parsing, and delivers corrected package code plus a one-table HTML summary. Use when a customer sends DBA AWR/SGA SQL Performance Summary, SGA+PGA Memory, Parameter Validation and Text Search extracts.
metadata:
  title: EBS Performance Review
  category: Performance Tuning
---

# EBS performance review

The deliverable is corrections, not a description of the load. Everything in the output must answer "what do we change, and is the change supplied or only described".

## Inputs to ask the customer for

All are Blitz Reports. Ask for them in one go, as XLSX, into one folder.

| Area | Report | Parameters |
|---|---|---|
| Memory | DBA SGA+PGA Memory Configuration | none. Also ask for `free -h` and `grep -i huge /proc/meminfo` from each node: the report's Hugepages column is its own recommendation (SGA GB x 512 + 5), not the current setting |
| Parameters | DBA Database Parameter Validation, DBA Parameters | none |
| Maintenance tasks | DBA Automated Maintenance Tasks | none |
| AWR settings | DBA AWR Settings | none |
| System load | DBA AWR Wait Event Summary, DBA AWR System Time Summary, DBA AWR System Metrics Summary | the full AWR window |
| Top SQL | DBA AWR SQL Performance Summary | the full AWR window (default retention is 8 days), top 200 by CPU |
| Literals | DBA SGA SQL Performance Summary | Literals Dupl Count >= 50 |
| Source | DBA Text Search | one run per package list; the report exports `dba_source` line by line for the packages named in the AWR `Code` column and the SGA module column |
| Waits, cache, result cache | DBA SGA Wait Event Summary (ASH), DBA SGA Buffer Cache Object Usage, DBA Result Cache Statistics, DBA Result Cache Objects and Dependencies, DBA Alert Log | none |
| Follow-up as needed | DBA AWR SQL Execution Plan History (per sql_id, plan hash blank), DBA AWR Active Session History, FND Concurrent Requests (per program), DBA Segments, DBA Table Modifications | |

On a multitenant database the AWR reports read the PDB only when `container_data` is `CURRENT` or `CURRENT_DICTIONARY`, and a PDB records no AWR data unless `awr_pdb_autoflush_enabled=true` is set in it. Tell the customer before the AWR runs: an empty or near-empty AWR extract means the parameter is off, and the data starts only from the next snapshot after it is set, so ask for it a few days ahead. With it, set the snapshot interval to 60 minutes (background in References, PDB AWR).

```sql
alter session set container=<PDB>;
alter system set awr_pdb_autoflush_enabled=true;
exec dbms_workload_repository.modify_snapshot_settings(interval=>60);
```

Lists of values for a report parameter (package names, sql_ids, program short names) are given as one semicolon-separated line with no spaces, ready to paste: `XXA_PKG;XXB_PKG`. Never split the values of one run into several lists (by program type, priority or module); explain any grouping in a sentence after the single line.

Do not ask the customer for anything you can answer from your own instances. Standard EBS index definitions, table types (global temporary or not), and column datatypes come from a 12.2 instance (see your environment file, `blitz-environment.md`), or from a local Vision instance. Standard `dba_source` for unwrapped Oracle packages likewise. The database parameters (`compatible`, `optimizer_features_enable`, every set parameter) are in the customer's Blitz Report installation logs (`database_parameters.log`): read them there instead of asking.

When the customer gives frontend access to a recent test clone, read source, view DDL, indexes, table statistics, data counts and the Blitz Report run history there yourself rather than asking for them: check its data dates first, since a clone refreshed recently answers the same questions as production. A clone restored from a production backup or a storage snapshot also keeps production's DBID and AWR repository, so it serves the AWR plans and history too: check `dba_hist_snapshot` per DBID and instance, and read only snapshots before the clone's `v$database.resetlogs_time`, since the clone keeps writing its own snapshots under the same DBID. Its `v$database.created` is production's creation date, not the clone date.

## Method

### 1. Configuration

- SGA: compare the SGA size row (the allocated SGA), `sga_max_size` and `pga_aggregate_target` to physical memory. In a pluggable database `sga_target` 0 means no limit of the PDB's own, not that automatic shared memory management is off; the container's value is the SGA size row. Often most of the memory is unallocated; the report's memory-unused figure is `physical - SGA size - pga_aggregate_target`, not free RAM, so confirm with `free -h`. Recommend using the memory the customer has already paid for, sized by calculation: physical memory minus about 5 GB for the OS, minus the memory of everything else on the host (other databases such as ASCP, ASM, clusterware), minus the expected maximum PGA (the PGA high-water mark over a few months plus 50%). Example: 128 GB, no RAC, ASM, ASCP or other database, PGA high-water mark 10 GB: 128 - 5 - 15 = 108 GB, so an SGA of up to about 100 GB. Most customers are constrained by memory, so go close to that limit; only where memory is plentiful and the other consumers are not yet known, stay well below it (1 TB of 1.5 TB). The calculation is always confirmed with the `free -h` and `grep -i huge /proc/meminfo` output of each node, which also shows whether hugepages need correcting. Never size by `v$sga_target_advice` or the SGA advice columns: a small estimated gain costs nothing on paid hardware and may be an infrequent but important online query. Recommend the `sga_target` increase up to `sga_max_size` first (dynamic, no restart), then a hugepage-backed increase with a rolling restart. With `use_large_pages=ONLY` the instance will not start if hugepages are short, so hugepages are sized before the SGA is raised (step by step in References, hugepages).
- PGA: never recommend a `pga_aggregate_limit`. EBS requires it at 0 (unlimited) so that no EBS process is terminated; raise `pga_aggregate_target` only.
- System statistics: the memory report shows `sys.aux_stats$` (record date, CPUSPEEDNW, IOSEEKTIM, IOTFRSPEED, MBRC). CPUSPEEDNW at the default 4096 means never gathered, or storage too fast for the NOWORKLOAD method; a record date before the last hardware or storage move means stale. Recommend `exec dbms_stats.gather_system_stats('noworkload')`, `'EXADATA'` on Exadata, or setting IOSEEKTIM and IOTFRSPEED with `dbms_stats.set_system_stats` when gathering leaves the defaults.
- System load: from the AWR wait event, time and metrics summaries over the full window. Never call a system CPU-bound because most of its database time is on CPU: it is CPU-bound only where the peak CPU use reaches the CPUs of the node (the Host CPU % and Foreground CPU % maximum columns of DBA AWR System Metrics Summary near 100). Database time that is not on CPU is itself a finding: User I/O and Cluster waits, and the Wait IO percentage of the memory report (I/O wait against I/O wait plus CPU time of the last week), are removed almost entirely by a larger SGA, so wherever memory is unallocated and the Wait IO percentage is above zero, recommend using the full memory, whatever the percentage: even 2% is waiting time that the available memory would remove, and the percentage only says how large the gain is. State load in average active sessions (time divided by the length of the AWR window) and counts per week, never as a bare number. High `log file sync`/`log file parallel write` times mean redo on slow storage; high `db file sequential read`/`scattered read` time supports the SGA increase; very high logical reads against modest physical reads point back to the top SQL, low physical read throughput with high read waits to slow disks.
- Parameters: check every set parameter against MOS KA1002 (formerly 396009.1, "Database Initialization Parameters for Oracle E-Business Suite Release 12"). Typical findings: `result_cache_max_size` 0 or too small, `_optim_peek_user_binds=FALSE` (never an EBS requirement; disables bind peeking database-wide and is behind most plan instability), parameters on the removal list still set, hidden parameters. Every parameter DBA Database Parameter Validation flags gets its statement in the configuration script and a row in a table in the review (parameter, current, required, action): set the mandatory ones, `alter system reset` every one on the removal list and every hidden parameter of section 3 (required value "Do not set hidden parameters"), with no "keep it if an SR asked for it" hedging, as the note and the analyzer say. `cursor_sharing=EXACT` is mandatory for EBS, so `FORCE` is never the fix for literals.
- Automated maintenance tasks: from DBA Automated Maintenance Tasks, every client enabled in a maintenance window. EBS requires `_optimizer_autostats_job=false` and the `auto optimizer stats collection` client disabled, with statistics gathered only by the Gather Schema Statistics concurrent request (FND), never by a database scheduler job; name the concurrent request explicitly in the review so it cannot be read as the database job (KA1002); auto space advisor and sql tuning advisor add IO and CPU with no usable result on EBS. Recommend `dbms_auto_task_admin.disable` per client, and `_addm_auto_enable=false` where no DBA reads ADDM findings. Check the AWR top SQL for `ORA$AT_*` jobs and `DBMS_STATS`/`DBMS_SQLTUNE` modules to show what they cost.
- Result cache: from the statistics report, invalidations per dependency object. A high count on `FND_PROFILE_OPTION_VALUES` or `FND_LOOKUP_VALUES` means something writes setup at runtime. Ask for `FND Profile Option Values` filtered on last update date in the last two days: Excel4apps stores each user's option blob in `XXE4A_OPTIONS00_*` profile values and rewrites it every session, and each write invalidates every cached profile result. The recommendation is then to replace it with Blitz Report.
- Editions: `select count(*) from dba_editions`. Online patching leaves one edition per cycle; above five, `SYS.OBJ$` grows by one row per editioned object per edition (33 editions gave 9.8 million rows against 432,000 on a one-edition instance) and every dictionary query the optimizer full-scans slows in proportion. Recommend `adop phase=prepare; actualize_all; finalize finalize_mode=full; cutover; cleanup cleanup_mode=full`, then `cleanup_mode=full` after every cycle.
- Which patch delivered a file version: on a 12.2 instance join `ad_files`, `ad_file_versions`, `ad_patch_run_bug_actions`, `ad_patch_run_bugs`, `ad_bugs`, `ad_patch_runs`, `ad_patch_drivers`, `ad_applied_patches` on the file name. The odf that defines a standard index is under `$PROD_TOP/patch/115/odf/`. A customer on an older release update pack can create the index with Oracle's own name and definition; the pack later finds it in place.

### 2. Top SQL

Work from the AWR extract's `Percentage` column (share of total DB CPU). Rules for reading it:

- One sql_id has one row per plan hash. Sum `Percentage` per sql_id; compute buffer gets per execution execution-weighted across plans, never as the worst plan's figure.
- AWR keeps only the top `topnsql` statements per category per snapshot (default 30 each by elapsed time, CPU, parse calls, sharable memory and version count; DBA AWR Settings shows it with the interval and retention). Frequent cheap statements can be missing; look for them in the SGA extract.
- Rows with null `Executions` and plan hash 0 are real cost with unavailable per-execution metrics; say so, do not print zero.
- `Blocks Exec` is buffer gets per execution; `Buffer IO` is MB (`db_block_size * buffer_gets / 1e6`).
- The `Code` and `Code Line#` columns name the PL/SQL unit and line; use them to find the statement in the Text Search extract. The `Module` column can be misattributed (workflow and forms personalisations set it and do not restore it).
- Verify every sql_id you cite exists in the extract. Transcription errors happen; one script over the final deliverables catches them.

For each statement in the top 100, classify it before doing anything else:

1. Custom PL/SQL with source supplied: correct the code. Read the whole procedure, not just the statement: the fix is often call volume (a lookup inside a per-row loop, a poll interval, a cursor that selects everything and rebuilds a table), not the statement's shape.
2. Custom PL/SQL without source: list the package for the next Text Search run. For every custom concurrent program whose source we lack, hand the customer ONE semicolon-separated list of concurrent program short names for the Blitz Report Custom Reports Converter in the same message as the other runs, rather than marking rows Needs input one by one; take the short names from the AWR `Module` (`e:<app>:cp:<appl>/<SHORT_NAME>`). Reports Builder runs show `rwrun@<host>` without the program: identify them with FND Concurrent Requests (Execution Method Oracle Reports, Started within Days = the AWR window, Running longer than x Minutes) and add their short names to the list. When the AWR `Module` is a concurrent program short name (`e:PO:cp:xxpo/XXPO_...`) rather than a package, the source comes through the Blitz Report Custom Reports Converter instead, which also gathers the report definitions, parameters and dependent objects. A program that is a report (Reports Builder, BI Publisher) is classified first. A data report (account analysis, revaluation, aging, any listing) always moves to a tuned Blitz Report: a library report where one covers it, else a conversion with the `migrate-custom-reports` skill, never a corrected rdf or data template. Only a printed document (pick and pack slip, commercial invoice, purchase order print) is corrected in place; a PL/SQL interface is treated as a package (for an `EXECUTION_METHOD_CODE='I'` program the converter gathers the package named in the executable's `EXECUTION_FILE_NAME`, whatever its prefix, plus its custom dependencies).
3. Oracle code: never edit. A plan baseline, an index check, a purge, or an SR.
4. External client (`.exe` modules): the SQL text is in AWR; supply the corrected predicate for the integration owner.
5. Oracle Alerts and Forms personalisations: setup changes, no package.

Patterns that recur:

- `col = NVL(:bind, col)` plus `(… AND :bind IS NULL) OR :bind IS NOT NULL`: two queries in one cursor. Rewrite as `(:b IS NOT NULL AND col = :b) OR (:b IS NULL AND col IS NOT NULL AND <range>)`; verify equivalence by truth table under three-valued logic, keep the `IS NOT NULL` that reproduces the null rejection.
- `DECODE(...)` on the inner side of an anti-join or a join: no index use. Split into one branch per case with a plain equality.
- `UPPER(col) = UPPER(:b)` on a dictionary or indexed column: drop the function on the column side.
- A self-join of `MTL_SUPPLY` on `SUPPLY_SOURCE_ID` alone: not unique without `SUPPLY_TYPE_CODE`.
- Setup or dictionary lookups inside a per-row loop: cache per request in a package associative array, cleared when `fnd_global.conc_request_id` changes. Same statement, same plan, fewer executions.
- `fnd_concurrent.wait_for_request` with `interval => 1`.
- `DELETE ... WHERE NVL(group_id,0) < 0` on `BOM_EXPLOSION_TEMP`: disables its indexes. It is a session-duration GTT: never recommend TRUNCATE.
- Twenty-plus plans for one sql_id: pin the cheapest observed plan with `dbms_spm.load_plans_from_cursor_cache` as a holding action; drop the baseline when the text is corrected.
- Copy-pasted statements: one sql_id with many source locations. Replace all copies; recommend one function as a follow-up.

### 3. Literals

From the SGA extract, `Literals Dupl Count` is `count(distinct sql_id)` per `force_matching_signature`: parent cursors, not child versions. Group families by owner (custom package, Oracle package, external client, form). For custom PL/SQL the fix is a bind in the `USING` clause; identifiers (table and column names) stay concatenated. Check the alert log for `too many parse errors` on the same families: a null id concatenated into text produces a statement that fails to parse on every call.

## Deliverables

Everything goes into one deliverables folder per review. Working files stay in a separate working folder.

1. `<Customer>_Performance_Review_<date>.html`. Structure, in this order and nothing else before it:
   - Section 1, one table: sql_id(s) colour-coded by status, % DB CPU, where, the defect (one to three sentences), the change (one to three sentences, file name if supplied), status. Statuses: Corrected (file supplied), Recommended (described, no file: DBA, setup, external), Needs input (say which run), Not analysed (source not supplied). Rows ordered by cost.
   - Section 2, how to deploy: files, order, what to test for each.
   - Section 3, what we still need: the runs, why, ranked. Never ask for what your own instances can answer.
   - Then one section per row: heading with sql_ids and %, one line on where it lives, `Defect`, `Solution`. Code excerpts single-spaced, in the customer's own formatting.
   - No load statistics sections, no module or theme rankings, no "what not to do" boxes, nothing about settings or code that stay as they are (a parameter left unlimited, a job that stays off), no "how to measure afterwards", no MOS citations in the body, no second numbering scheme (no "Finding N" alongside section numbers).
2. `package_code/`: for every corrected package, `<PKG>.pkb` (verbatim from the Text Search extract) and `<PKG>_corrected.pkb`, never a `.diff` (the reader compares with their own tool). CRLF, no BOM. Generate with `scripts/gen_pairs.py`; edits are line-range replacements so the original is provably untouched elsewhere. Match the customer's code style, not your own. Comments state why the code is shaped as it is, never what changed.
3. `notes_and_scripts/`: only what the DBA applies: the parameter changes, the index DDL, corrected statements for external clients. No check scripts, verification or test queries, and nothing that asks for what is already known (current parameters come from the installation log and DBA SGA+PGA Memory Configuration); what is genuinely missing is asked for as a Blitz Report run in section 3.
4. `<Customer>_SQL_Findings_<date>.xlsx`: every statement with full metrics, for the customer to filter.
5. `blitz_reports/`: the import XML of every custom report rebuilt as a Blitz Report, with a note (`notes_and_scripts/NN`) listing per report what changed, the parameter mapping and the row comparison against the original SQL on your test instance.

The zip handed to the customer holds only what they deploy or run: the review html, the corrected files each next to its original, and the scripts. Its root is the folder level of the html and the subfolders, with no wrapping folder; no diffs, no README, no working files.

The covering email opens with the CPU the customer saves, summed by script from the section 1 rows: "In short, the corrections and recommendations in it address the statements behind **X% of the database's total CPU time** (Y% with corrected code supplied, Z% with the fix described); applying them should remove most of that load." Y is the Corrected rows, Z the Recommended rows, X their sum; the points that follow quote the same figures.

Before publishing, run the checks in `scripts/verify_deliverables.py`: every cited sql_id exists in the extracts, no control characters, no BOM, CRLF on `.pkb`, no `.diff` file, every section reference resolves, no banned words.

## Verification without a database

The customer's instance is not reachable. Compensate:

- Bracket balance and BEGIN/END counts on every corrected body.
- Truth tables for predicate rewrites, under Oracle three-valued logic, over every combination of bind and column nullness.
- Standard index and table definitions from your own 12.2 instance.
- Every numeric claim recomputed from the extract by script, not typed.
- Adversarial review of any rewrite: a second pass whose only job is to refute it.
- Match the SQL syntax to the customer's `compatible` setting from the installation log: EBS 12.2 sites on 19c often run `compatible=12.1.0`, which rejects `validate_conversion`, `default ... on conversion error`, `listagg(distinct ...)` and `listagg ... on overflow` with `ORA-00907`. Corrected code, check scripts and test queries must use 12.1 syntax there (`regexp_like` tests, `case when regexp_like(x,'^[0-9]+$') then to_number(x) end`).

## Scripts

`scripts/extract_xlsx.py` turns the Blitz XLSX extracts into JSON. `scripts/gen_pairs.py` is the original/corrected generator with the line-range edit model. `scripts/master_table.py` builds the section-1 table from a row list and the AWR JSON. `scripts/verify_deliverables.py` is the pre-publish check. Copy them into the working folder and adapt the paths and row lists.

## References

Blog posts to send the customer with the recommendation they support.

- Hugepages: https://www.enginatics.com/blog/how-to-configure-hugepages-for-oracle-ebs/ — sizing, `sysctl` and memlock settings, `use_large_pages=ONLY`, CDB and PDB SGA parameters, and large pages on non-Linux platforms.
- PDB AWR: https://www.enginatics.com/blog/updated-dba-awr-blitz-reports-now-work-with-plugglable-databases/ — `awr_pdb_autoflush_enabled`, snapshot interval, `container_data` and the reports' container parameter.
