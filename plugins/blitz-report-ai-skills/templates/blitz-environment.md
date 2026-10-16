# Blitz Report Environment

The Blitz Report skills read this file to reach your Oracle EBS instances. Keep it in your project as `.claude/rules/blitz-environment.md` so it loads in every session. Never put production credentials here: use `$APPS_PWD` and other environment variables, set in your shell.

## Instances

| Role | Connect | Notes |
|---|---|---|
| development instance | `<host>:<port>/<service>` | EBS release and database version, `XXEN_TOP`, `APPLCSF`, where the apps tier environment file is |
| conversion instance | | Where migrated reports (Custom Reports Converter, Discoverer) are built and tested; often the development instance |
| 11i instance | | Only when you develop content for EBS 11i |

Never develop or test on production. The skills submit reports and uploads, compile packages and import content on the development instance.

## Database access

How Claude runs SQL on the development instance, for example the Oracle SQLcl MCP server (`sql -mcp`) with a saved connection, or SQLcl/SQL*Plus from the shell: `sql -S apps/$APPS_PWD@<host>:<port>/<service>`.

## Apps tier access

How Claude reaches the apps tier, if at all (SSH user and host, key authentication). Without apps tier access, content is imported over SQL with `xxen_api.import_xml(<clob>)` and request output is fetched with `xxen_util.concurrent_request_file_url(<request_id>)`.

## Deploy

- Content XML: on the apps tier `cd <dir> && $XXEN_TOP/bin/import_xml $APPS_PWD <file>.xml`, or over SQL `xxen_api.import_xml(<clob>)`.
- PL/SQL: compile the spec before the body, `set define off`, then `show errors`.

## Session initialisation for tests

```sql
fnd_global.apps_initialize(<user_id>,<responsibility_id>,<application_id>);
mo_global.init('<application short name>');
```

Test user, responsibilities, operating unit, ledger, inventory organization and open periods on the development instance:
