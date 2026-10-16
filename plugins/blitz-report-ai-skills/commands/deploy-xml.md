---
description: "Deploy XML to the Development Instance: Import Blitz Report XML definition files to the development instance (see `blitz-environment.md` for how to reach it)."
---

# Deploy XML to the Development Instance

Import Blitz Report XML definition files to the development instance (see `blitz-environment.md` for how to reach it).

## Instructions

1. If $ARGUMENTS specifies a file, use that. Otherwise, identify modified XML files from git status under `content/`
2. For each XML file to deploy (uploads: also lint the XML with `${CLAUDE_PLUGIN_ROOT}/scripts/lint_upload_xml.py` before the import and check every LOV parses after it — the deploy procedure in `blitz-environment.md`):
   - Copy the file to a working directory on the apps tier of the development instance (e.g. `/tmp`)
   - Import from that directory: `cd /tmp && $XXEN_TOP/bin/import_xml $APPS_PWD <filename>`
   - Without apps-tier access, import the file content from a database session with `xxen_api.import_xml(<clob>)`
3. Check the import output for errors
4. Report results

## Important

- Always use the standard import script (`$XXEN_TOP/bin/import_xml`) or `xxen_api.import_xml`, never direct SQL on the `xxen_*` tables
- The import script handles initialization, error handling, and logging properly
- XML filenames should match what's in the content directory
