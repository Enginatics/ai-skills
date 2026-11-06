---
name: br-skill-author
description: >
  Write a new Blitz Report Excel skill or extend one of the shipped br-* skills: interview the user
  for the business question, discover the exact report names, parameters and list values live from
  the connected Oracle EBS instance, write a complete SKILL.md in the shipped format into a
  worksheet, and give the steps to install it in Copilot in Excel or Claude in Excel. Use when the
  user asks for their own skill, wants to turn a prompt they repeat into a skill, wants other
  thresholds, their own reports or another output in an existing skill, or says 'make a skill for',
  'customise the holds analysis', 'add our report to the skill'. Writes nothing to Oracle EBS.
# Trigger: Slash command + auto
---

# Blitz Report Skill Author (br-skill-author)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.

A skill is a folder named exactly as the `name` in its SKILL.md frontmatter; the frontmatter holds
the `name` and a `description`, the body holds the instructions. Copilot in Excel reads the folder
from the user's OneDrive skills folder, Claude in Excel from a zip of it uploaded to the user's
Claude account. The assistant picks a skill by its description, so the description decides whether
the skill fires at all. You cannot write files: you write the file text into a worksheet and the
user saves it.

**Requires:** br-run-reports (discovery mechanics). Read `references/skill-template.md` before
writing and `references/install-and-extend.md` before the hand-over.

## Step 1 — Interview (one message, only what is missing)
1. The question the skill answers, in the user's words, with two or three example prompts (they go
   into the description).
2. Module and responsibility; the inputs every run needs (organization, operating unit, ledger,
   period, date window) and which may default.
3. What comes back: a ranked list, a red/amber/green scorecard, a dashboard, a count; and the
   decision the user takes with it.
4. Thresholds and rules (days overdue, amount floors, categories to exclude). A value the user does
   not know becomes a labelled placeholder in CONFIG, never a silent guess.
5. Whether the skill should also change Oracle EBS data (release, update, create). If yes it is an
   action skill: it delegates every write to br-run-uploads and asks for confirmation twice.
Do not write anything before the answers are in.

## Step 2 — New skill, or extension of a shipped one
- A shipped br-* skill already covers the question (holds, close readiness, collections, stock
  levels, BOM, WIP, payments, duplicates) and the user wants other thresholds, their own reports,
  another output or a narrower scope: extend it. Ask the user to paste that skill's SKILL.md into a
  sheet named `skill_source` (column A, one line per row; Copilot users open it from the OneDrive
  skills folder, Claude users from the downloaded zip), or to describe the change. Keep the shipped
  structure and change only what was asked.
- Anything else: a new skill from the template.
- Names: lower-case words joined by hyphens, with the customer's own prefix instead of `br-`
  (`acme-ap-holds-3-months`). An extension gets a new name too: a folder named `br-*` is replaced
  when the shipped skills are updated, so edits inside it are lost. Folder name = frontmatter name.

## Step 3 — Discover the reports live (helper sheet `blitz_`; never activate it; delete it at the end)
Every report name, parameter name and fixed list value in the skill comes from the instance, never
from memory. The user's own reports sit in the same library and are found the same way.
- `=br_report_list_external("<words>")` lists candidates (`Type = U` rows are uploads, used only by
  the action section). Nothing found: match the full library as br-report-finder does.
- `=br_report_params_external("<Report Name>")` gives the exact parameter spellings, `Must Set?`,
  `Multiple` and `Has LOV`; the skill passes parameters with these spellings only.
- `=br_param_values_external("<Report Name>","<Parameter>")` gives the exact spelling of any value
  the skill hard-codes (a status, a period type, a hold type): write the `Value` column as shown.
- `=br_report_templates_external("<Report Name>")` when the skill needs a particular column set.
- `#BLITZ_NOT_CONNECTED`: ask the user to connect through the Blitz Report ribbon. `#SPILL!`: clear
  space and retry.
Do not run a report while authoring. Column names come from a short run only when the user asks
for it, with the narrowest parameters that still return rows.

## Step 4 — Write the SKILL.md
Fill `references/skill-template.md`. The generated text keeps these rules:
- Frontmatter `name` = folder name; `description` = what it does, the user's own trigger phrases,
  and `WRITES to Oracle EBS` only for an action skill.
- The data banner and the delegation sentences (extraction by br-run-reports, writes by
  br-run-uploads) verbatim from the template. The generated skill never calls the worksheet
  functions itself except through those two skills.
- A `Reports used` table with exact names and the parameters passed; the fallback search only on
  `#BLITZ_REPORT_NOT_FOUND`.
- CONFIG with every threshold and its status (confirmed by the user, or placeholder until confirmed);
  the summary sheet the skill writes shows the assumptions.
- A numbered pipeline, one workbook operation per step; analytics as Excel formulas (Copilot runs no
  scripts); named output sheets in tab order; a Validation section with the tie-out; a 'Talk in the
  user's language' section.
- An analysis skill never writes to Oracle EBS. An action skill: proposal, confirmation 1, fill and
  validate, confirmation 2, submit; never a write without both.
- No double quote character anywhere in the text (Excel wraps such a cell in quotes when it is
  copied, and the quotes land in the file): single quotes or backticks instead. No tab characters.
- SKILL.md under about 10 KB; longer detail goes to `references/<topic>.md`, named in the SKILL.md.

## Step 5 — Hand over
Add a sheet named after the skill and write the file text into column A from A1, one line of the
file per row, the column formatted as text, nothing else on the sheet. A second file (such as
`references/thresholds.md`) goes on its own sheet named `<skill-name> references thresholds`. Then
give the user the install steps from `references/install-and-extend.md` for their assistant, in
their words, and the first prompt to try. Copilot in Excel may show a Save skill card for the text once
it is complete: tell the user to save it there, which writes the folder into their skills folder and
lists the skill under Custom skills at once. Delete `blitz_`.

## Validation (before the hand-over)
- Every report, parameter and list value in the text appeared in a discovery spill of this session.
- Folder name equals the frontmatter name; the description contains the user's trigger phrases.
- No double quote characters, no tabs, no worksheet function names outside the fixed banner.
- No data from the instance in the text (the skill travels with the user's OneDrive): names of
  reports, parameters and settings only, never values from report rows.

## Talk in the user's language
'I will write the skill as a text sheet that you save as SKILL.md', 'the skill runs the AP Invoice
on Hold report and ranks the holds'. Never mention `blitz_`, the worksheet functions or the spill.
