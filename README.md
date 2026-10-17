# Enginatics AI Skills for Oracle E-Business Suite

AI skills for [Blitz Report](https://www.enginatics.com), maintained by Enginatics and used daily by our own development team. Skills and rules here update with every Blitz Report release. This repository is generated; send feedback to support@enginatics.com.

| Plugin | For | Works with |
|---|---|---|
| `blitz-report-ai-skills` | Developers: build, convert, test and tune Blitz Reports and Blitz Uploads | Claude Code |
| `blitz-report-excel-addin-ai-skills` | Business users: run EBS business processes from Excel through the Blitz Report add-in | Claude in Excel, Microsoft 365 Copilot in Excel |

```
/plugin marketplace add enginatics/ai-skills
/plugin install blitz-report-ai-skills@enginatics
/plugin install blitz-report-excel-addin-ai-skills@enginatics
```

To receive updates automatically, enable auto-update for the `enginatics` marketplace in `/plugin` > Marketplaces, or run `/plugin marketplace update enginatics`.

## Development skills

Run `/blitz-report-ai-skills:blitz-environment-setup` once. It creates `.claude/rules/blitz-environment.md` in your project, describing how Claude reaches your EBS development instance. Never point it at production.

Main workflows:

| Command | What it does |
|---|---|
| `/blitz-report-ai-skills:migrate-custom-reports` | Turns the zip from the Blitz Report Custom Reports Converter into Blitz Reports on your conversion instance |
| `/blitz-report-ai-skills:convert-report` | Converts an Oracle RDF, BI Publisher or concurrent program report into a Blitz Report |
| `/blitz-report-ai-skills:build-upload` | Builds a Blitz Upload (XML and PL/SQL package) from an Oracle form or API |
| `/blitz-report-ai-skills:review-upload`, `/blitz-report-ai-skills:test-upload` | Reviews an upload against the Oracle form and tests it end to end |
| `/blitz-report-ai-skills:test-report` | Compares a converted report's output with the original |
| `/blitz-report-ai-skills:tune-report-performance` | Finds and fixes expensive report SQL |

The plugin also carries the rules our team works by (coding standards, report and upload development, EBS API patterns, 11i compatibility, migrations); Claude loads them when the task needs them.

Requirements: Blitz Report installed on the EBS development instance, and database access from Claude Code to that instance (Oracle SQLcl MCP server, SQLcl or SQL*Plus).

## Excel add-in skills

The skills run inside Excel through the Blitz Report Excel add-in. Run `/blitz-report-excel-addin-ai-skills:excel-skills-setup` to install or update them in Claude in Excel or Microsoft 365 Copilot in Excel and to see which skill does what.

Without Claude Code:
- Claude in Excel: upload `plugins/blitz-report-excel-addin-ai-skills/zips/<name>.zip` (Customize > Skills > Create skill).
- Microsoft 365 Copilot in Excel: copy the folder `plugins/blitz-report-excel-addin-ai-skills/excel-skills/<name>` into `Documents/Copilot/Microsoft Excel/Skills` in your OneDrive.
- All skill folders in one zip: `blitz-report-excel-addin-ai-skills.zip` in the latest release.

## License

MIT, see [LICENSE](LICENSE). You may use, adapt and redistribute the skills, for example as reference material for your own assistant, keeping the copyright notice.

## Feedback

support@enginatics.com
