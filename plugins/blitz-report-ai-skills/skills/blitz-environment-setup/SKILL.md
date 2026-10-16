---
name: blitz-environment-setup
description: Set up the Blitz Report environment file (.claude/rules/blitz-environment.md) that the Blitz Report development skills use to reach the Oracle EBS development instance. Use on first use of the Blitz Report skills, when a skill cannot find blitz-environment.md, or when the user wants to change instance, connection or deploy details.
---

# Blitz Report Environment Setup

1. Look for `.claude/rules/blitz-environment.md` in the project. If it exists, show the user its instance table and ask what to change.
2. Otherwise copy `${CLAUDE_PLUGIN_ROOT}/templates/blitz-environment.md` there and fill it in with the user, one section at a time:
   - development instance: host, port, service, EBS release, database version. Confirm Blitz Report is installed: `select xxen_report.version from dual` (or any `xxen_api` call) must work.
   - database access: prefer the Oracle SQLcl MCP server with a saved connection; otherwise SQLcl or SQL*Plus from the shell. Test the connection with a `select` from `fnd_product_groups`.
   - apps tier access: SSH or none.
   - test user and responsibilities for `fnd_global.apps_initialize`, resolved from one row of `fnd_user_resp_groups_direct` joined to `fnd_responsibility_vl`.
3. Never write a password into the file. Use `$APPS_PWD` and tell the user to set it in their shell.
4. Refuse to configure a production instance as the development or conversion instance.
