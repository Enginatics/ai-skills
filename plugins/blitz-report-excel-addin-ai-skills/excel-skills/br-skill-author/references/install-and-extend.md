# Installing, testing and extending a skill

Give the user the part for their assistant, in their words.

## From the worksheet to a file
1. On the sheet named after the skill, select column A (click the column header), copy, paste into
   Notepad or VS Code, and check the first and last lines: a line starting or ending with a stray
   quote character means a double quote slipped into the text; remove it in the editor.
2. Save as `SKILL.md` with UTF-8 encoding inside a new folder named exactly like the skill
   (`acme-ap-holds-3-months`). A second file from a sheet named `<skill-name> references <topic>`
   is saved as `references/<topic>.md` inside that folder.

## Copilot in Excel
When the Copilot pane shows a Save skill card after the text is written, Save skill writes the folder
into the skills folder and the skill appears under Custom skills at once; the steps below are the manual
route.
1. Copilot pane > Settings (the three dots) > Manage plugins & skills > Custom skills > Open skills
   folder. This is `Documents/Copilot/Microsoft Excel/skills` in the OneDrive of the account that
   licenses Office.
2. Move the skill folder there and wait until OneDrive shows it synced.
3. Select Refresh in the Custom skills dialog. The skill appears under its name; switch it on, or
   name it in the prompt with `@<skill-name>`, which runs it even while it shows as off.
4. Where the Copilot pane offers the `@skill-builder` skill, the text can also be handed to it with
   'save this as a skill named <skill-name>' instead of steps 1 to 3.

## Claude in Excel
Claude in Excel uses the skills of the user's Claude account; the upload is done in Claude on the web,
not in the Excel pane.
1. Right-click the skill folder > Compress to ZIP file. The zip holds the folder itself at the top
   level (`<skill-name>/SKILL.md`), not the loose files.
2. claude.ai > Customize > Skills > + > Create skill > Upload a skill, and choose the zip. Check that
   its switch is on. `br-analytics-standards` and `br-run-reports` must be uploaded too, once.
3. Skills need code execution: Settings > Capabilities > Code execution and file creation; on a Team
   or Enterprise plan the owner turns it on for the organization.
4. In the Claude pane in Excel, type / to see the skill, or ask the first example prompt.

## First run and what to fix
Open a new workbook, connect the Blitz Report add-in to the environment with the responsibility the
skill needs, and ask the first example prompt from the description.
- The skill did not fire: name it (`@<skill-name> ...` in Copilot, `/` in the Claude pane), then
  sharpen the description with the words the user actually used.
- A report was not found: the name in the `Reports used` table differs from the library; copy the
  exact name from the add-in's report list.
- A parameter was rejected: its spelling differs from the run screen; copy it from the parameter
  list of the report.
- Zero rows: the responsibility has no access to the organization, operating unit or ledger, or a
  date parameter defaulted to today; set the input explicitly or switch responsibility.
- The summary does not tie: a column header in a formula is not the header on the raw sheet.
Every fix is an edit of SKILL.md followed by Refresh (Copilot), or for Claude by deleting the skill
under Customize > Skills (the ... menu next to its switch) and uploading the new zip.

## Extending a shipped br-* skill
1. Copy the shipped folder to a new name with the customer's prefix and change `name` in the
   frontmatter to match; the shipped folder stays as delivered and is replaced by later updates.
2. Safe to change: `description` (add the user's phrases), the `Reports used` table (the customer's
   own report in place of the shipped one, keeping the columns the pipeline reads, or named in the
   pipeline where they differ), every value under `CONFIG`, output sheet names and order, the
   narrative, the scope (a date window, an organization, a category).
3. Keep as they are: the data banner, the division of responsibility, the delegation to
   br-run-reports, and for action skills the two confirmations and the single column the skill
   writes.
4. The user's own report must carry the parameters the pipeline passes and the columns it reads;
   check both with the report's parameter list and a short run before changing the table.

## Sharing with colleagues
Copilot reads each user's own OneDrive skills folder: copy the folder to each colleague's skills
folder, or distribute it as the Microsoft 365 administrator does for the organization. For Claude
in Excel each user uploads the zip once, or the owner of a Team or Enterprise plan provisions it
for everyone: Organization settings > Plugins & skills > Add > Upload a skill. Keep one copy of the
folder as the master and send the whole folder, never a SKILL.md alone, when it has a `references`
folder.
