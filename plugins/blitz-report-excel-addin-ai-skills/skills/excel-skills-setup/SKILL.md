---
name: excel-skills-setup
description: Install the Blitz Report Excel add-in AI skills into Claude in Excel or Microsoft 365 Copilot in Excel, update them, and explain which skill fits a task. Use when the user wants to install, update or list the Blitz Report Excel skills, asks what they can do, or asks which skill to use for an Oracle EBS task in Excel.
---

# Blitz Report Excel Add-in Skills Setup

The skills in this plugin run inside Excel, not in this session: they call the Blitz Report Excel add-in, which reads and writes Oracle E-Business Suite. This skill installs them and explains them.

`references/skills.md` lists every skill by category with what it does. Skills marked `writes to EBS` change Oracle data, always after the user confirms in Excel; all others only read.

## Prerequisites

Check with the user, do not assume:
1. Blitz Report is installed on their Oracle EBS instance.
2. The Blitz Report Excel add-in is installed and connects (Blitz Report ribbon > Login). Installation: https://www.enginatics.com/blitz-report-user-guide/
3. They use Claude in Excel, or Microsoft 365 Copilot in Excel with a Copilot licence.

## Install or update

Ask which skills they want: all of them, a category from `references/skills.md`, or named skills. Every skill is self-contained, so any subset works.

Claude in Excel:
1. Each skill is a zip in `${CLAUDE_PLUGIN_ROOT}/zips/<name>.zip`. Copy the chosen zips to a folder the user names (default: a `Blitz Report Excel Skills` folder in their Downloads) and open that folder for them.
2. Tell them to upload each zip in Claude: Customize > Skills > Create skill > Upload. To update a skill, delete the old one there first and upload the new zip.

Microsoft 365 Copilot in Excel:
1. The skills folder is `Documents/Copilot/Microsoft Excel/skills` in the OneDrive of the account Office is licensed by, for a work and a personal account alike; Copilot creates it with Copilot pane > Settings > Manage plugins & skills > Custom skills > Create OneDrive folder. Locally it is under that account's OneDrive folder (`OneDriveCommercial`, `OneDriveConsumer` or `OneDrive` environment variable on Windows) when the OneDrive client syncs the account. Confirm the folder with the user before writing to it.
2. Copy each chosen folder from `${CLAUDE_PLUGIN_ROOT}/excel-skills/<name>/` into it, replacing a folder of the same name. Leave other folders there alone. The folder name must stay equal to the skill name or Copilot does not load it.
3. Once OneDrive has synced, select Refresh in the Custom skills dialog. Custom skills need the Office display language set to English; no Custom skills section at all means the account has no Copilot licence. No Copilot button although the account has a licence: Office is licensed by another account; File > Account > Product Information names it, Switch License changes it.

After a plugin update (`/plugin marketplace update enginatics`), run this skill again to refresh the installed copies.

## First use

Suggest starting with `br-run-reports` (run any Blitz Report into the workbook) or `br-report-finder` (find the report for a question), then a skill from the user's own area in `references/skills.md`. In Excel the user just asks in plain language, for example "analyse my AP holds" or "is GL ready to close for this period".
